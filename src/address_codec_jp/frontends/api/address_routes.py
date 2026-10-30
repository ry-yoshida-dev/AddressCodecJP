from typing import Annotated

from fastapi import APIRouter, Path, Query
from fastapi.responses import JSONResponse
from geo_coordinate import GeodeticCrs

from address_codec_jp.address_codec import AddressCodec
from address_codec_jp.frontends.api.batch_request import BatchRequest
from address_codec_jp.frontends.api.codec_pool import CodecPool
from address_codec_jp.frontends.api.dataset_coverage import DatasetCoverage
from address_codec_jp.frontends.api.format_parameters import FormatParameters
from address_codec_jp.frontends.api.input_interpreter import InputInterpreter
from address_codec_jp.frontends.api.invalid_request_error import InvalidRequestError
from address_codec_jp.frontends.api.query.answer import QueryAnswer
from address_codec_jp.frontends.api.query.handler import QueryHandler
from address_codec_jp.frontends.api.query.operation import QueryOperation
from address_codec_jp.frontends.api.query.options import QueryOptions
from address_codec_jp.frontends.api.service_settings import ServiceSettings
from address_codec_jp.frontends.serialization import EnumName, JsonValue

type CrsName = Annotated[str, Query(description="tokyo, jgd2000, jgd2011, or wgs84.")]
type CoordinateQuery = Annotated[
    str, Query(description="latitude,longitude in decimal degrees.", min_length=1)
]
type AddressQuery = Annotated[str, Query(description="Address in any notation.", min_length=1)]
type CodePath = Annotated[str, Path(description="Address code such as 131016-0011001-2-3.")]


class AddressRoutes:
    """
    HTTP endpoints of the web API, version 1.

    Every successful response carries ``attribution``, the credits of the datasets it
    is derived from. Points and shapes tell with ``is_exact`` whether they stand for the
    requested address itself.

    Parameters
    ----------
    pool : CodecPool
        Worker threads that run the queries.
    settings : ServiceSettings
        Batch size limit and coverage policy.
    """

    def __init__(self, pool: CodecPool, settings: ServiceSettings) -> None:
        self._pool: CodecPool = pool
        self._settings: ServiceSettings = settings
        self._crs_name: EnumName[GeodeticCrs] = EnumName(GeodeticCrs)
        self._operation_name: EnumName[QueryOperation] = EnumName(QueryOperation)
        self._interpreter: InputInterpreter = InputInterpreter()

    def build_router(self) -> APIRouter:
        """
        Build the router of the endpoints.

        Returns
        -------
        APIRouter
            Endpoints under ``/v1`` and ``/health``.
        """
        router = APIRouter()
        _ = router.get("/health")(self.health)
        _ = router.get("/v1/codes")(self.encode)
        _ = router.get("/v1/codes/{code}")(self.decode)
        _ = router.get("/v1/codes/{code}/location")(self.locate_code)
        _ = router.get("/v1/codes/{code}/area")(self.find_area_code)
        _ = router.get("/v1/codes/{code}/children")(self.list_children)
        _ = router.get("/v1/locations")(self.locate)
        _ = router.get("/v1/nearest")(self.find_nearest)
        _ = router.get("/v1/postal-codes/{postal_code}")(self.list_by_postal_code)
        _ = router.get("/v1/areas")(self.find_area)
        _ = router.get("/v1/areas-at")(self.find_areas_at)
        _ = router.post("/v1/batch")(self.run_batch)
        return router

    async def health(self) -> JSONResponse:
        """
        Report that the service can answer, with the municipalities it holds.

        Returns
        -------
        JSONResponse
            ``status`` and the numbers of municipalities with lots and boundaries.
        """

        def describe(codec: AddressCodec, coverage: DatasetCoverage) -> dict[str, JsonValue]:
            return {
                "status": "ok",
                "lot_municipality_count": len(coverage.lot_municipality_codes),
                "boundary_municipality_count": len(coverage.boundary_municipality_codes),
                "imported_dataset_count": len(codec.list_imports()),
            }

        return JSONResponse(await self._pool.run(describe))

    async def encode(
        self,
        *,
        address: AddressQuery,
        is_lot_verified: Annotated[bool, Query(alias="verify_lot")] = False,
    ) -> JSONResponse:
        """
        Encode an address.

        Parameters
        ----------
        address : AddressQuery
            Address in any notation.
        is_lot_verified : bool
            Whether the lot numbers must be registered.

        Returns
        -------
        JSONResponse
            ``code``, ``level``, ``remainder``, and ``town_name_tier``.
        """
        options = QueryOptions(is_lot_verified=is_lot_verified)
        return await self._respond(QueryOperation.ENCODE, address, options)

    async def decode(
        self, *, code: CodePath, address_format: Annotated[FormatParameters, Query()]
    ) -> JSONResponse:
        """
        Decode a code.

        Parameters
        ----------
        code : CodePath
            Address code.
        address_format : FormatParameters
            Format of the address.

        Returns
        -------
        JSONResponse
            ``code`` and ``address``.
        """
        options = QueryOptions(address_format=address_format.to_address_format())
        return await self._respond(QueryOperation.DECODE, code, options)

    async def locate(self, *, address: AddressQuery, crs: CrsName = "jgd2011") -> JSONResponse:
        """
        Find the representative point of an address.

        Parameters
        ----------
        address : AddressQuery
            Address in any notation.
        crs : CrsName
            Datum of the point.

        Returns
        -------
        JSONResponse
            ``code``, ``located_code``, ``level``, ``is_exact``, ``latitude``,
            ``longitude``, and ``crs``.
        """
        options = QueryOptions(crs=self._parse_crs(crs))
        return await self._respond(QueryOperation.LOCATE, address, options)

    async def locate_code(self, *, code: CodePath, crs: CrsName = "jgd2011") -> JSONResponse:
        """
        Find the representative point of a code.

        Parameters
        ----------
        code : CodePath
            Address code.
        crs : CrsName
            Datum of the point.

        Returns
        -------
        JSONResponse
            Same fields as ``locate``.
        """
        options = QueryOptions(crs=self._parse_crs(crs))
        return await self._respond(QueryOperation.LOCATE_CODE, code, options)

    async def find_nearest(
        self,
        *,
        coordinate: CoordinateQuery,
        crs: CrsName = "jgd2011",
        max_distance_meters: Annotated[float, Query(alias="max_distance", gt=0)] = 1000.0,
    ) -> JSONResponse:
        """
        Find the address nearest to a coordinate.

        Parameters
        ----------
        coordinate : CoordinateQuery
            ``latitude,longitude``.
        crs : CrsName
            Datum of the coordinate and of the returned point.
        max_distance_meters : float
            Largest accepted distance.

        Returns
        -------
        JSONResponse
            ``code``, ``address``, ``level``, ``latitude``, ``longitude``,
            ``distance_meters``, and ``crs``.
        """
        options = QueryOptions(crs=self._parse_crs(crs), max_distance_meters=max_distance_meters)
        return await self._respond(QueryOperation.NEAREST, coordinate, options)

    async def list_by_postal_code(
        self,
        *,
        postal_code: Annotated[str, Path(description="Postal code such as 100-0005.")],
        address_format: Annotated[FormatParameters, Query()],
    ) -> JSONResponse:
        """
        List the towns of a postal code.

        Parameters
        ----------
        postal_code : str
            Postal code.
        address_format : FormatParameters
            Format of the addresses.

        Returns
        -------
        JSONResponse
            ``towns``, each with its ``code`` and ``address``.
        """
        options = QueryOptions(address_format=address_format.to_address_format())
        return await self._respond(QueryOperation.POSTAL, postal_code, options)

    async def list_children(
        self, *, code: CodePath, address_format: Annotated[FormatParameters, Query()]
    ) -> JSONResponse:
        """
        List the registered areas directly under a code.

        Parameters
        ----------
        code : CodePath
            Prefecture, municipality, or town code.
        address_format : FormatParameters
            Format of the addresses.

        Returns
        -------
        JSONResponse
            ``code`` and ``children``, each with its ``code``, ``address``, and
            ``level``; empty for a chome or koaza.
        """
        options = QueryOptions(address_format=address_format.to_address_format())
        return await self._respond(QueryOperation.CHILDREN, code, options)

    async def find_area(
        self,
        *,
        address: AddressQuery,
        is_geometry_included: Annotated[bool, Query(alias="geometry")] = True,
    ) -> JSONResponse:
        """
        Find the shape of an address.

        Parameters
        ----------
        address : AddressQuery
            Address in any notation.
        is_geometry_included : bool
            Whether the GeoJSON geometry is written.

        Returns
        -------
        JSONResponse
            ``code``, ``located_code``, ``level``, ``is_exact``, ``sources``, and
            ``geometry``.
        """
        options = QueryOptions(is_geometry_included=is_geometry_included)
        return await self._respond(QueryOperation.AREA, address, options)

    async def find_area_code(
        self,
        *,
        code: CodePath,
        is_geometry_included: Annotated[bool, Query(alias="geometry")] = True,
    ) -> JSONResponse:
        """
        Find the shape of a code.

        Parameters
        ----------
        code : CodePath
            Address code.
        is_geometry_included : bool
            Whether the GeoJSON geometry is written.

        Returns
        -------
        JSONResponse
            Same fields as ``find_area``.
        """
        options = QueryOptions(is_geometry_included=is_geometry_included)
        return await self._respond(QueryOperation.AREA_CODE, code, options)

    async def find_areas_at(
        self,
        *,
        coordinate: CoordinateQuery,
        crs: CrsName = "jgd2011",
        is_parcel_included: Annotated[bool, Query(alias="parcels")] = False,
        is_geometry_included: Annotated[bool, Query(alias="geometry")] = False,
    ) -> JSONResponse:
        """
        List the towns, and optionally parcels, that contain a coordinate.

        Parameters
        ----------
        coordinate : CoordinateQuery
            ``latitude,longitude``.
        crs : CrsName
            Datum of the coordinate.
        is_parcel_included : bool
            Whether land parcels are listed besides towns.
        is_geometry_included : bool
            Whether the GeoJSON geometries are written.

        Returns
        -------
        JSONResponse
            ``areas``, each with its ``code``, ``address``, ``level``, ``sources``, and
            optionally ``geometry``.
        """
        options = QueryOptions(
            crs=self._parse_crs(crs),
            is_parcel_included=is_parcel_included,
            is_geometry_included=is_geometry_included,
        )
        return await self._respond(QueryOperation.AREAS_AT, coordinate, options)

    async def run_batch(self, request: BatchRequest) -> JSONResponse:
        """
        Apply one operation to many inputs.

        Parameters
        ----------
        request : BatchRequest
            Operation, inputs, and options.

        Returns
        -------
        JSONResponse
            ``results`` in input order; a failed input carries ``error``,
            ``error_type``, and its HTTP ``status`` instead of result fields.

        Raises
        ------
        InvalidRequestError
            If there are more inputs than ``ServiceSettings.max_batch_size``, or an
            option names no member.
        """
        if len(request.inputs) > self._settings.max_batch_size:
            raise InvalidRequestError(
                f"A batch takes at most {self._settings.max_batch_size} inputs, "
                + f"got {len(request.inputs)}."
            )
        operation = self._interpreter.interpret(self._operation_name.parse, request.operation)
        options = QueryOptions(
            address_format=request.address_format.to_address_format(),
            is_lot_verified=request.is_lot_verified,
            crs=self._parse_crs(request.crs),
            max_distance_meters=request.max_distance_meters,
            is_parcel_included=request.is_parcel_included,
            is_geometry_included=request.is_geometry_included,
        )
        inputs = list(request.inputs)

        def answer(codec: AddressCodec, coverage: DatasetCoverage) -> QueryAnswer:
            return self._handler(codec, coverage).answer_each(operation, inputs, options)

        return JSONResponse((await self._pool.run(answer)).to_json())

    async def _respond(
        self, operation: QueryOperation, input_text: str, options: QueryOptions
    ) -> JSONResponse:
        def answer(codec: AddressCodec, coverage: DatasetCoverage) -> QueryAnswer:
            return self._handler(codec, coverage).answer(operation, input_text, options)

        return JSONResponse((await self._pool.run(answer)).to_json())

    def _parse_crs(self, crs: str) -> GeodeticCrs:
        return self._interpreter.interpret(self._crs_name.parse, crs)

    def _handler(self, codec: AddressCodec, coverage: DatasetCoverage) -> QueryHandler:
        return QueryHandler(
            codec,
            coverage,
            publisher=self._settings.publisher,
            is_coverage_required=self._settings.is_coverage_required,
        )
