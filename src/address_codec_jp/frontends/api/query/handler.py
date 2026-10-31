from collections.abc import Iterable
from typing import ClassVar

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
from address_codec_jp.frontends.api.query.coverage_guard import CoverageGuard
from address_codec_jp.frontends.query import (
    PassThroughGuard,
    QueryGuard,
    QueryOperation,
    QueryOptions,
    QueryRecord,
    QueryRunner,
)
from address_codec_jp.frontends.serialization import ErrorSerializer, JsonValue
from address_codec_jp.results import AreaSource


class QueryHandler:
    """
    Executor of web API queries on the codec of a worker thread.

    Queries run through ``QueryRunner`` with an ``InputInterpreter``, which reports
    malformed inputs as invalid, and with ``is_coverage_required`` a ``CoverageGuard``,
    which rejects municipalities the cache does not hold. An input longer than
    ``max_input_length``, or one whose numbers are too large to look up, is rejected as
    invalid.

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
    max_input_length : int
        Largest number of characters of one input.
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
        max_input_length: int,
    ) -> None:
        self._codec: AddressCodec = codec
        guard: QueryGuard = (
            CoverageGuard(codec, coverage) if is_coverage_required else PassThroughGuard()
        )
        self._runner: QueryRunner = QueryRunner(codec, InputInterpreter(), guard)
        self._credit_writer: CreditWriter = CreditWriter(
            codec, publisher, coverage.registry_map_dates
        )
        self._max_input_length: int = max_input_length
        self._error_serializer: ErrorSerializer = ErrorSerializer()
        self._error_status: ErrorStatus = ErrorStatus()

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
            If the input is malformed or too long.
        LookupError
            If nothing is found; ``AmbiguousAddressError`` if several areas fit.
        DatasetNotImportedError
            If the data needed is not prepared.
        """
        record = self._run_checked(operation, input_text, options)
        return QueryAnswer(
            {"input": input_text, **record.fields},
            self._write_credits(self._attributions_of(record)),
        )

    def answer_each(
        self, operation: QueryOperation, inputs: list[str], options: QueryOptions
    ) -> QueryAnswer:
        """
        Run one query per input, reporting failures in place of their results.

        Failures caused by an input, including data not prepared for it, are reported in
        place; a fault of the server fails the whole request.

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
                record = self._run_checked(operation, input_text, options)
            except self._INPUT_ERRORS as error:
                results.append(
                    {
                        "input": input_text,
                        "status": int(self._error_status.of(error)),
                        **self._error_serializer.serialize(error),
                    }
                )
                continue
            results.append({"input": input_text, **record.fields})
            attributions.update(self._attributions_of(record))
        return QueryAnswer({"results": results}, self._write_credits(attributions))

    def _run_checked(
        self, operation: QueryOperation, input_text: str, options: QueryOptions
    ) -> QueryRecord:
        if len(input_text) > self._max_input_length:
            raise InvalidRequestError(
                f"An input takes at most {self._max_input_length} characters, "
                + f"got {len(input_text)}."
            )
        try:
            return self._runner.run(operation, input_text, options)
        except OverflowError as error:
            raise InvalidRequestError("A number in the input is too large to look up.") from error

    def _attributions_of(self, record: QueryRecord) -> frozenset[DataAttribution]:
        attributions = set(self._REGISTRY)
        if record.lot_code is not None:
            attributions.update(self._parcel_master_of(record.lot_code))
        for area in record.areas:
            if AreaSource.CENSUS_BOUNDARY in area.sources:
                attributions.add(DataAttribution(DataSource.CENSUS_BOUNDARY))
            if AreaSource.REGISTRY_MAP in area.sources:
                attributions.add(DataAttribution(DataSource.REGISTRY_MAP, area.code.lg_code))
        return frozenset(attributions)

    def _parcel_master_of(self, code: AddressCode) -> frozenset[DataAttribution]:
        if not code.is_lot:
            return frozenset()
        town = self._codec.resolve(code).town
        if town is not None and LotSystem.LAND_PARCEL not in town.lot_systems:
            return frozenset()
        return frozenset({DataAttribution(DataSource.PARCEL_MASTER, code.lg_code)})

    def _write_credits(self, attributions: Iterable[DataAttribution]) -> tuple[str, ...]:
        return tuple(self._credit_writer.write(attributions))
