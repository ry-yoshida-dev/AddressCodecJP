from typing import ClassVar

from geo_coordinate import GeoCoordinate, GeodeticCrs

from address_codec_jp.domain.address_area import AddressArea
from address_codec_jp.domain.address_code import AddressCode
from address_codec_jp.domain.area_shape import AreaShape
from address_codec_jp.domain.area_source import AreaSource
from address_codec_jp.domain.lot_system import LotSystem
from address_codec_jp.errors.area_not_found_error import AreaNotFoundError
from address_codec_jp.errors.dataset_not_imported_error import DatasetNotImportedError
from address_codec_jp.positioning.datum_converter import DatumConverter
from address_codec_jp.positioning.position_source import PositionSource
from address_codec_jp.storage.area_record import AreaRecord
from address_codec_jp.storage.area_repository import AreaRepository


class AreaFinder:
    """
    Finder of the shape of an address code and of the shapes around a coordinate.

    Lot numbers are looked up in the registry maps only for towns numbered by land
    parcels, or whose numbering is unknown, because block and residence numbers of the
    residence indication have no published shapes. A town without a shape falls back to
    its oaza, an oaza without a shape of its own is made of the shapes of its chome or
    koaza, and a municipality of the shapes of all its towns. Prefectures have no shape.

    Parameters
    ----------
    areas : AreaRepository
        Imported area shapes.
    positions : PositionSource
        Imported points, which tell the numbering system of a town.
    """

    _SEARCH_DATUM: ClassVar[GeodeticCrs] = GeodeticCrs.JGD2011

    def __init__(self, areas: AreaRepository, positions: PositionSource) -> None:
        self._areas: AreaRepository = areas
        self._positions: PositionSource = positions
        self._converter: DatumConverter = DatumConverter()

    def find(self, code: AddressCode) -> AddressArea:
        """
        Find the shape of an address code.

        Parameters
        ----------
        code : AddressCode
            Address code to look up.

        Returns
        -------
        AddressArea
            Shape of the code or of its nearest enclosing area that has one.

        Raises
        ------
        DatasetNotImportedError
            If no shape has been imported.
        AreaNotFoundError
            If neither the code nor any enclosing area below the prefecture has a shape.
        """
        if not self._areas.is_area_imported:
            raise DatasetNotImportedError("No area shapes have been imported.")
        for candidate in code.lineage():
            found = self._find_record(candidate)
            if found is not None:
                return AddressArea(
                    code=code,
                    located_code=candidate,
                    shape=found.shape,
                    sources=frozenset({found.source}),
                )
        raise AreaNotFoundError(f"No area shape is imported for {code} or its enclosing areas.")

    def list_at(
        self, coordinate: GeoCoordinate, crs: GeodeticCrs, *, is_parcel_included: bool
    ) -> list[AddressArea]:
        """
        List the shapes that contain a coordinate.

        Parameters
        ----------
        coordinate : GeoCoordinate
            Coordinate on ``crs``.
        crs : GeodeticCrs
            Datum of ``coordinate``.
        is_parcel_included : bool
            Whether land parcels are listed besides towns.

        Returns
        -------
        list[AddressArea]
            Towns first, then land parcels, each ordered by code.

        Raises
        ------
        DatasetNotImportedError
            If no shape has been imported.
        RuntimeError
            If ``crs`` cannot be transformed.
        """
        if not self._areas.is_area_imported:
            raise DatasetNotImportedError("No area shapes have been imported.")
        searched = self._converter.transform(coordinate, crs, self._SEARCH_DATUM)
        records = self._areas.list_containing(
            float(searched.longitude.degree.flat[0]), float(searched.latitude.degree.flat[0])
        )
        sources = [
            AreaSource.CENSUS_BOUNDARY,
            *([AreaSource.REGISTRY_MAP] if is_parcel_included else []),
        ]
        return [
            AddressArea(
                code=record.code,
                located_code=record.code,
                shape=record.shape,
                sources=frozenset({record.source}),
            )
            for source in sources
            for record in records
            if record.source is source
        ]

    def _find_record(self, code: AddressCode) -> AreaRecord | None:
        if code.machiaza_id is None:
            if AddressCode.is_prefecture_code(code.lg_code):
                return None
            return self._combine(code, f"{code.lg_code}-")
        if code.lot.numbers:
            if not self._is_parcel_numbered(code.lg_code, code.machiaza_id):
                return None
            return self._find_stored(code, AreaSource.REGISTRY_MAP)
        stored = self._find_stored(code, AreaSource.CENSUS_BOUNDARY)
        if stored is not None:
            return stored
        if code.machiaza_id.endswith("000"):
            return self._combine(code, f"{code.lg_code}-{code.machiaza_id[:4]}")
        return None

    def _find_stored(self, code: AddressCode, source: AreaSource) -> AreaRecord | None:
        shape = self._areas.find(code, source)
        return None if shape is None else AreaRecord(code=code, source=source, shape=shape)

    def _combine(self, code: AddressCode, code_prefix: str) -> AreaRecord | None:
        records = self._areas.list_by_prefix(code_prefix, AreaSource.CENSUS_BOUNDARY)
        if not records:
            return None
        return AreaRecord(
            code=code,
            source=AreaSource.CENSUS_BOUNDARY,
            shape=AreaShape(
                tuple(polygon for record in records for polygon in record.shape.polygons)
            ),
        )

    def has_parcel_shape(self, code: AddressCode) -> bool:
        """
        Tell whether the shape of a code is looked up in the registry maps.

        Parameters
        ----------
        code : AddressCode
            Address code.

        Returns
        -------
        bool
            ``True`` for lot numbers of a town numbered by land parcels, or whose
            numbering is unknown.
        """
        if code.machiaza_id is None or not code.lot.numbers:
            return False
        return self._is_parcel_numbered(code.lg_code, code.machiaza_id)

    def _is_parcel_numbered(self, lg_code: str, machiaza_id: str) -> bool:
        town = self._positions.find_town(lg_code, machiaza_id)
        return town is None or town.lot_system is LotSystem.LAND_PARCEL
