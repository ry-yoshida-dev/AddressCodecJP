from typing import assert_never

from geo_coordinate import GeoCoordinate

from address_codec_jp.address import AddressCode
from address_codec_jp.address_codec import AddressCodec
from address_codec_jp.errors import AddressNotFoundError, AreaNotFoundError, PositionNotFoundError
from address_codec_jp.frontends.query.guard import QueryGuard
from address_codec_jp.frontends.query.operation import QueryOperation
from address_codec_jp.frontends.query.options import QueryOptions
from address_codec_jp.frontends.query.record import QueryRecord
from address_codec_jp.frontends.query.text_interpreter import TextInterpreter
from address_codec_jp.frontends.serialization import CoordinateText, ResultRows, ResultSerializer


class QueryRunner:
    """
    Answers a ``QueryOperation`` on one text input, for the command line and the web API.

    Both front ends answer through this class, so a query reads the same datasets and
    gives the same fields in both. An empty postal code, name, or coordinate listing is
    reported as not found. The ``interpreter`` decides how parse errors are reported,
    and the ``guard`` which datasets a query may read.

    Parameters
    ----------
    codec : AddressCodec
        Codec that answers the queries.
    interpreter : TextInterpreter
        Parse error reporting of the front end.
    guard : QueryGuard
        Dataset checks of the front end.
    """

    def __init__(
        self, codec: AddressCodec, interpreter: TextInterpreter, guard: QueryGuard
    ) -> None:
        self._codec: AddressCodec = codec
        self._interpreter: TextInterpreter = interpreter
        self._guard: QueryGuard = guard
        self._serializer: ResultSerializer = ResultSerializer(codec)
        self._rows: ResultRows = ResultRows(self._serializer)
        self._coordinate_text: CoordinateText = CoordinateText()

    def run(self, operation: QueryOperation, input_text: str, options: QueryOptions) -> QueryRecord:
        """
        Answer one input.

        Parameters
        ----------
        operation : QueryOperation
            Query to answer.
        input_text : str
            Address, code, postal code, name, or ``latitude,longitude``.
        options : QueryOptions
            Options of the query.

        Returns
        -------
        QueryRecord
            Fields and rows of the answer, with the lot and shapes it was drawn from.

        Raises
        ------
        ValueError
            If the input is malformed, unless the interpreter reports it otherwise.
        LookupError
            If nothing is found; ``AmbiguousAddressError`` if several areas fit.
        DatasetNotImportedError
            If the data needed has not been imported or the guard rejects it.
        """
        codec = self._codec
        interpreter = self._interpreter
        guard = self._guard
        serializer = self._serializer
        rows = self._rows
        address_format = options.address_format
        match operation:
            case QueryOperation.ENCODE:
                address_match = interpreter.interpret(codec.match, input_text)
                lot_code: AddressCode | None = None
                if options.is_lot_verified:
                    lot_code = address_match.code
                    guard.require_lots(lot_code)
                    codec.verify_lot(lot_code)
                return QueryRecord(
                    serializer.match(address_match),
                    lambda: rows.match(address_match),
                    lot_code=lot_code,
                )
            case QueryOperation.DECODE:
                decoded = serializer.render(self._parse_code(input_text), address_format)
                return QueryRecord(serializer.decoded(decoded), lambda: rows.address(decoded))
            case QueryOperation.LOCATE:
                return self._locate(self._encode(input_text), options)
            case QueryOperation.LOCATE_CODE:
                return self._locate(self._parse_code(input_text), options)
            case QueryOperation.NEAREST:
                return self._find_nearest(self._parse_coordinate(input_text), options)
            case QueryOperation.POSTAL:
                addresses = interpreter.interpret(codec.list_by_postal_code, input_text)
                if not addresses:
                    raise AddressNotFoundError(f"No town is registered with {input_text!r}.")
                towns = serializer.render_all(addresses, address_format)
                return QueryRecord({"towns": serializer.towns(towns)}, lambda: rows.towns(towns))
            case QueryOperation.CHILDREN:
                children = serializer.render_all(
                    interpreter.interpret(codec.list_children, input_text), address_format
                )
                return QueryRecord(
                    {
                        "code": str(self._parse_code(input_text)),
                        "children": serializer.listed_areas(children),
                    },
                    lambda: rows.listed_areas(children),
                )
            case QueryOperation.NAME:
                addresses = interpreter.interpret(codec.list_by_name, input_text)
                if not addresses:
                    raise AddressNotFoundError(f"No area is named {input_text!r}.")
                named_areas = serializer.render_all(addresses, address_format)
                return QueryRecord(
                    {"name": input_text, "areas": serializer.listed_areas(named_areas)},
                    lambda: rows.listed_areas(named_areas),
                )
            case QueryOperation.AREA:
                return self._find_area(self._encode(input_text), options)
            case QueryOperation.AREA_CODE:
                return self._find_area(self._parse_code(input_text), options)
            case QueryOperation.AREAS_AT:
                areas = codec.find_areas_at(
                    self._parse_coordinate(input_text),
                    options.crs,
                    is_parcel_included=options.is_parcel_included,
                )
                if not areas:
                    raise AreaNotFoundError(f"No imported area shape contains {input_text!r}.")
                guard.require_areas_at(areas, is_parcel_included=options.is_parcel_included)
                is_geometry_included = options.is_geometry_included
                return QueryRecord(
                    {"areas": serializer.areas(areas, is_geometry_included=is_geometry_included)},
                    lambda: rows.areas(areas, is_geometry_included=is_geometry_included),
                    areas=tuple(areas),
                )
            case _:
                assert_never(operation)

    def _parse_code(self, input_text: str) -> AddressCode:
        return self._interpreter.interpret(AddressCode.parse, input_text)

    def _parse_coordinate(self, input_text: str) -> GeoCoordinate:
        return self._interpreter.interpret(self._coordinate_text.parse, input_text)

    def _encode(self, input_text: str) -> AddressCode:
        return self._interpreter.interpret(self._codec.encode, input_text)

    def _locate(self, code: AddressCode, options: QueryOptions) -> QueryRecord:
        self._guard.require_lots(code)
        location = self._codec.locate_code(code, options.crs)
        return QueryRecord(
            self._serializer.location(location),
            lambda: self._rows.location(location),
            lot_code=location.located_code,
        )

    def _find_nearest(self, coordinate: GeoCoordinate, options: QueryOptions) -> QueryRecord:
        try:
            nearest = self._codec.find_nearest(coordinate, options.crs, options.max_distance_meters)
        except PositionNotFoundError:
            self._guard.require_nearby_lots(coordinate, options, None)
            raise
        self._guard.require_nearby_lots(coordinate, options, nearest)
        address = self._serializer.render(nearest.code).address
        return QueryRecord(
            self._serializer.nearest(nearest, address),
            lambda: self._rows.nearest(nearest, address),
            lot_code=nearest.code,
        )

    def _find_area(self, code: AddressCode, options: QueryOptions) -> QueryRecord:
        self._guard.require_area(code)
        area = self._codec.find_area_code(code)
        is_geometry_included = options.is_geometry_included
        return QueryRecord(
            self._serializer.area(area, is_geometry_included=is_geometry_included),
            lambda: self._rows.area(area, is_geometry_included=is_geometry_included),
            areas=(area,),
        )
