from collections.abc import Iterable
from typing import ClassVar, assert_never

from geo_coordinate import GeoCoordinate

from address_codec_jp.address import AddressCode, LotSystem
from address_codec_jp.address_codec import AddressCodec
from address_codec_jp.errors import (
    AddressNotFoundError,
    AmbiguousAddressError,
    AreaNotFoundError,
    DatasetNotImportedError,
    PositionNotFoundError,
    ReadingNotFoundError,
)
from address_codec_jp.frontends.api.credit_writer import CreditWriter
from address_codec_jp.frontends.api.data_attribution import DataAttribution
from address_codec_jp.frontends.api.data_source import DataSource
from address_codec_jp.frontends.api.dataset_coverage import DatasetCoverage
from address_codec_jp.frontends.api.error_status import ErrorStatus
from address_codec_jp.frontends.api.input_interpreter import InputInterpreter
from address_codec_jp.frontends.api.invalid_request_error import InvalidRequestError
from address_codec_jp.frontends.api.query.answer import QueryAnswer
from address_codec_jp.frontends.api.query.operation import QueryOperation
from address_codec_jp.frontends.api.query.options import QueryOptions
from address_codec_jp.frontends.api.query.result import QueryResult
from address_codec_jp.frontends.serialization import (
    CoordinateText,
    ErrorSerializer,
    JsonValue,
    ResultSerializer,
)
from address_codec_jp.results import AddressArea, AreaSource


class QueryHandler:
    """
    Executor of web API queries on the codec of a worker thread.

    With ``is_coverage_required``, a query that needs the lots or boundaries of a
    municipality that the cache does not hold fails with ``DatasetNotImportedError``
    instead of silently falling back to an enclosing area, because the service never
    downloads them on use.

    Parameters
    ----------
    codec : AddressCodec
        Codec of the current thread.
    coverage : DatasetCoverage
        Municipalities the cache holds.
    publisher : str
        Organization that processes and serves the data, named in the credits.
    is_coverage_required : bool
        Whether missing municipalities are rejected.
    """

    _REGISTRY: ClassVar[frozenset[DataAttribution]] = frozenset(
        {DataAttribution(DataSource.ADDRESS_BASE_REGISTRY)}
    )

    _INPUT_ERRORS: ClassVar[tuple[type[Exception], ...]] = (
        AddressNotFoundError,
        AmbiguousAddressError,
        AreaNotFoundError,
        PositionNotFoundError,
        ReadingNotFoundError,
        DatasetNotImportedError,
        InvalidRequestError,
    )

    def __init__(
        self,
        codec: AddressCodec,
        coverage: DatasetCoverage,
        *,
        publisher: str,
        is_coverage_required: bool,
    ) -> None:
        self._codec: AddressCodec = codec
        self._credit_writer: CreditWriter = CreditWriter(
            codec, publisher, coverage.registry_map_dates
        )
        self._coverage: DatasetCoverage = coverage
        self._is_coverage_required: bool = is_coverage_required
        self._serializer: ResultSerializer = ResultSerializer(codec)
        self._error_serializer: ErrorSerializer = ErrorSerializer()
        self._error_status: ErrorStatus = ErrorStatus()
        self._coordinate_text: CoordinateText = CoordinateText()
        self._interpreter: InputInterpreter = InputInterpreter()

    def answer(
        self, operation: QueryOperation, input_text: str, options: QueryOptions
    ) -> QueryAnswer:
        """
        Run one query.

        Parameters
        ----------
        operation : QueryOperation
            Query to run.
        input_text : str
            Address, code, postal code, or ``latitude,longitude``.
        options : QueryOptions
            Options of the query.

        Returns
        -------
        QueryAnswer
            ``input`` and the result fields, with the datasets to credit.

        Raises
        ------
        InvalidRequestError
            If the input is malformed.
        LookupError
            If nothing is found; ``AmbiguousAddressError`` if several areas fit.
        DatasetNotImportedError
            If the data needed is not prepared.
        """
        result = self._run(operation, input_text, options)
        return QueryAnswer(
            {"input": input_text, **result.fields}, self._write_credits(result.attributions)
        )

    def answer_each(
        self, operation: QueryOperation, inputs: list[str], options: QueryOptions
    ) -> QueryAnswer:
        """
        Run one query per input, reporting failures in place of their results.

        Only failures caused by an input are reported in place; a fault of the server
        fails the whole request.

        Parameters
        ----------
        operation : QueryOperation
            Query to run.
        inputs : list[str]
            Inputs of the queries.
        options : QueryOptions
            Options shared by the queries.

        Returns
        -------
        QueryAnswer
            ``results`` in input order, each the fields of ``answer`` or of the error
            with its HTTP ``status``, with the datasets to credit.
        """
        results: list[JsonValue] = []
        attributions: set[DataAttribution] = set(self._REGISTRY)
        for input_text in inputs:
            try:
                result = self._run(operation, input_text, options)
            except self._INPUT_ERRORS as error:
                results.append(
                    {
                        "input": input_text,
                        "status": int(self._error_status.of(error)),
                        **self._error_serializer.serialize(error),
                    }
                )
                continue
            results.append({"input": input_text, **result.fields})
            attributions.update(result.attributions)
        return QueryAnswer({"results": results}, self._write_credits(attributions))

    def _run(
        self, operation: QueryOperation, input_text: str, options: QueryOptions
    ) -> QueryResult:
        match operation:
            case QueryOperation.ENCODE:
                address_match = self._codec.match(self._require_address(input_text))
                if not options.is_lot_verified:
                    return QueryResult(self._serializer.match(address_match), self._REGISTRY)
                self._require_lots(address_match.code)
                address_match = self._codec.match(input_text, is_lot_verified=True)
                return QueryResult(
                    self._serializer.match(address_match),
                    self._REGISTRY | self._parcel_master_of(address_match.code),
                )
            case QueryOperation.DECODE:
                fields: dict[str, JsonValue] = {
                    "code": str(self._parse_code(input_text)),
                    **self._serializer.decoded(input_text, options.address_format),
                }
                return QueryResult(fields, self._REGISTRY)
            case QueryOperation.LOCATE:
                return self._locate(self._encode(input_text), options)
            case QueryOperation.LOCATE_CODE:
                return self._locate(self._parse_code(input_text), options)
            case QueryOperation.NEAREST:
                nearest = self._codec.find_nearest(
                    self._parse_coordinate(input_text),
                    options.crs,
                    options.max_distance_meters,
                )
                if self._is_coverage_required:
                    self._coverage.require_lots(nearest.code.lg_code)
                return QueryResult(
                    self._serializer.nearest(nearest),
                    self._REGISTRY | self._parcel_master_of(nearest.code),
                )
            case QueryOperation.POSTAL:
                addresses = self._interpreter.interpret(self._codec.list_by_postal_code, input_text)
                if not addresses:
                    raise AddressNotFoundError(f"No town is registered with {input_text!r}.")
                return QueryResult(
                    self._serializer.towns(addresses, options.address_format), self._REGISTRY
                )
            case QueryOperation.CHILDREN:
                children = self._interpreter.interpret(self._codec.list_children, input_text)
                fields = {
                    "code": str(self._parse_code(input_text)),
                    **self._serializer.children(children, options.address_format),
                }
                return QueryResult(fields, self._REGISTRY)
            case QueryOperation.AREA:
                return self._area(self._encode(input_text), options)
            case QueryOperation.AREA_CODE:
                return self._area(self._parse_code(input_text), options)
            case QueryOperation.AREAS_AT:
                areas = self._codec.find_areas_at(
                    self._parse_coordinate(input_text),
                    options.crs,
                    is_parcel_included=options.is_parcel_included,
                )
                if not areas:
                    raise AreaNotFoundError(f"No prepared area shape contains {input_text!r}.")
                return QueryResult(
                    self._serializer.areas(
                        areas, is_geometry_included=options.is_geometry_included
                    ),
                    self._attributions_of(areas),
                )
            case _:
                assert_never(operation)

    def _parse_code(self, input_text: str) -> AddressCode:
        return self._interpreter.interpret(AddressCode.parse, input_text)

    def _parse_coordinate(self, input_text: str) -> GeoCoordinate:
        return self._interpreter.interpret(self._coordinate_text.parse, input_text)

    def _encode(self, input_text: str) -> AddressCode:
        return self._codec.encode(self._require_address(input_text))

    def _require_address(self, input_text: str) -> str:
        if not input_text.strip():
            raise InvalidRequestError("Address must not be blank.")
        return input_text

    def _locate(self, code: AddressCode, options: QueryOptions) -> QueryResult:
        self._require_lots(code)
        location = self._codec.locate_code(code, options.crs)
        return QueryResult(
            self._serializer.location(location),
            self._REGISTRY | self._parcel_master_of(location.located_code),
        )

    def _area(self, code: AddressCode, options: QueryOptions) -> QueryResult:
        if self._is_coverage_required:
            self._coverage.require_boundaries(code.lg_code)
        area = self._codec.find_area_code(code)
        fields = self._serializer.area(area, is_geometry_included=options.is_geometry_included)
        return QueryResult(fields, self._attributions_of([area]))

    def _require_lots(self, code: AddressCode) -> None:
        if self._is_coverage_required and code.machiaza_id is not None and code.lot.numbers:
            self._coverage.require_lots(code.lg_code)

    def _parcel_master_of(self, code: AddressCode) -> frozenset[DataAttribution]:
        if code.machiaza_id is None or not code.lot.numbers:
            return frozenset()
        town = self._codec.resolve(code).town
        if town is not None and LotSystem.LAND_PARCEL not in town.lot_systems:
            return frozenset()
        return frozenset({DataAttribution(DataSource.PARCEL_MASTER, code.lg_code)})

    def _attributions_of(self, areas: list[AddressArea]) -> frozenset[DataAttribution]:
        attributions = set(self._REGISTRY)
        for area in areas:
            if AreaSource.CENSUS_BOUNDARY in area.sources:
                attributions.add(DataAttribution(DataSource.CENSUS_BOUNDARY))
            if AreaSource.REGISTRY_MAP in area.sources:
                attributions.add(DataAttribution(DataSource.REGISTRY_MAP, area.code.lg_code))
        return frozenset(attributions)

    def _write_credits(self, attributions: Iterable[DataAttribution]) -> tuple[str, ...]:
        return tuple(self._credit_writer.write(attributions))
