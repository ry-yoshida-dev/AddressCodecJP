from typing import ClassVar

from geo_coordinate import GeoCoordinate, GeodeticCrs

from address_codec_jp.address import AddressCode
from address_codec_jp.database.storage import AreaRepository, PositionRepository, TownRepository
from address_codec_jp.errors import AddressNotFoundError, DatasetNotImportedError
from address_codec_jp.geocoding.address_locator import AddressLocator
from address_codec_jp.geocoding.area_finder import AreaFinder
from address_codec_jp.geocoding.dataset_supplier import DatasetSupplier
from address_codec_jp.geocoding.nearest_address_finder import NearestAddressFinder
from address_codec_jp.results import AddressArea, AddressLocation, NearestAddress


class Geocoder:
    """
    Geocoder of address codes and coordinates that adds missing datasets before a lookup.

    Each lookup first asks the supplier for the per-municipality datasets it may need:
    the lots of a code, the lots of the municipalities around a coordinate, or the
    shapes of the municipality of a code or around a coordinate. Without a supplier,
    only the imported datasets are used.

    The registry lists the lot numbers of a Kyoto street direction
    (``Town.is_street_direction``) under its oaza, so a street direction with lot
    numbers is verified, located, and shaped as the same lot numbers of its oaza when
    the registry lists that oaza.

    Parameters
    ----------
    towns : TownRepository
        Imported towns, to find the oaza of a street direction.
    positions : PositionRepository
        Imported points and lot numbers.
    areas : AreaRepository
        Imported area shapes.
    supplier : DatasetSupplier | None
        Provider of missing datasets, or ``None`` to use only what has been imported.
    """

    NEARBY_LOT_MARGIN_METERS: ClassVar[float] = 5000.0
    NEARBY_AREA_RADII_METERS: ClassVar[tuple[float, ...]] = (1000.0, 5000.0)

    def __init__(
        self,
        towns: TownRepository,
        positions: PositionRepository,
        areas: AreaRepository,
        supplier: DatasetSupplier | None,
    ) -> None:
        self._towns: TownRepository = towns
        self._positions: PositionRepository = positions
        self._areas: AreaRepository = areas
        self._supplier: DatasetSupplier | None = supplier
        self._street_municipality_codes: set[str] | None = None
        self._locator: AddressLocator = AddressLocator(positions)
        self._nearest_finder: NearestAddressFinder = NearestAddressFinder(positions)
        self._area_finder: AreaFinder = AreaFinder(areas, positions)

    def verify_lot(self, code: AddressCode) -> None:
        """
        Fail unless the lot numbers of a code are registered.

        Codes without lot numbers always pass.

        Parameters
        ----------
        code : AddressCode
            Code to verify.

        Raises
        ------
        AddressNotFoundError
            If no lot of the town is imported or its lot numbers are not registered.
        DatasetNotImportedError
            If no block, residence, or parcel master has been imported.
        """
        code = self._to_lot_owner(code)
        if code.machiaza_id is None or not code.is_lot:
            return
        self._ensure_lots(code)
        if not self._positions.is_lot_imported:
            raise DatasetNotImportedError(
                "No block, residence, or parcel master has been imported to verify lot numbers."
            )
        if not self._positions.has_lots(code.lg_code, code.machiaza_id):
            raise AddressNotFoundError(
                f"No block, residence, or parcel of {code} has been imported."
            )
        if not self._positions.contains_lot(code.lg_code, code.machiaza_id, code.lot):
            raise AddressNotFoundError(f"Lot numbers of {code} are not registered.")

    def locate(self, code: AddressCode, crs: GeodeticCrs) -> AddressLocation:
        """
        Find the representative point of a code, adding the lots of its municipality first.

        Parameters
        ----------
        code : AddressCode
            Address code to locate.
        crs : GeodeticCrs
            Datum of the returned coordinate.

        Returns
        -------
        AddressLocation
            Point of the code, or of its nearest enclosing area that has one.
        """
        code = self._to_lot_owner(code)
        self._ensure_lots(code)
        return self._locator.locate(code, crs)

    def find_nearest(
        self, coordinate: GeoCoordinate, crs: GeodeticCrs, max_distance_meters: float
    ) -> NearestAddress:
        """
        Find the nearest address, adding the lots of the nearby municipalities first.

        Parameters
        ----------
        coordinate : GeoCoordinate
            Searched coordinate on ``crs``.
        crs : GeodeticCrs
            Datum of ``coordinate`` and of the returned point.
        max_distance_meters : float
            Largest accepted distance to a representative point.

        Returns
        -------
        NearestAddress
            Code, point, and distance of the nearest address.
        """
        if self._supplier is not None and max_distance_meters > 0:
            self._supplier.ensure_lots(
                self.list_nearby_municipalities(coordinate, crs, max_distance_meters)
            )
        return self._nearest_finder.find(coordinate, crs, max_distance_meters)

    def list_nearby_municipalities(
        self, coordinate: GeoCoordinate, crs: GeodeticCrs, max_distance_meters: float
    ) -> set[str]:
        """
        List the municipalities whose lots ``find_nearest`` may return.

        Parameters
        ----------
        coordinate : GeoCoordinate
            Searched coordinate on ``crs``.
        crs : GeodeticCrs
            Datum of ``coordinate``.
        max_distance_meters : float
            Largest accepted distance to a representative point.

        Returns
        -------
        set[str]
            Local government codes of the municipalities whose town points lie within
            ``max_distance_meters`` plus ``NEARBY_LOT_MARGIN_METERS``.

        Raises
        ------
        ValueError
            If ``max_distance_meters`` is not positive.
        """
        if not max_distance_meters > 0:
            raise ValueError(f"max_distance_meters must be positive, got {max_distance_meters}.")
        return self._nearest_finder.list_nearby_municipalities(
            coordinate, crs, max_distance_meters + self.NEARBY_LOT_MARGIN_METERS
        )

    def has_parcel_shape(self, code: AddressCode) -> bool:
        """
        Tell whether the shape of a code is looked up in the registry maps.

        Parameters
        ----------
        code : AddressCode
            Address code to check.

        Returns
        -------
        bool
            ``True`` for lot numbers of a town numbered by land parcels, or whose
            numbering is unknown.
        """
        return self._area_finder.has_parcel_shape(self._to_lot_owner(code))

    def find_area(self, code: AddressCode) -> AddressArea:
        """
        Find the shape of a code, adding the shapes of its municipality first.

        The registry maps are added only when the shape of the code is a land parcel.

        Parameters
        ----------
        code : AddressCode
            Address code to look up.

        Returns
        -------
        AddressArea
            Shape of the code, or of its nearest enclosing area that has one.
        """
        code = self._to_lot_owner(code)
        if self._supplier is not None and not AddressCode.is_prefecture_code(code.lg_code):
            self._supplier.ensure_areas(
                [code.lg_code], is_parcel_included=self._area_finder.has_parcel_shape(code)
            )
        return self._area_finder.find(code)

    def find_areas_at(
        self, coordinate: GeoCoordinate, crs: GeodeticCrs, *, is_parcel_included: bool
    ) -> list[AddressArea]:
        """
        Find the shapes that contain a coordinate, adding the nearby shapes first.

        The town boundaries of the municipalities whose town points lie within the first
        of ``NEARBY_AREA_RADII_METERS`` are added first, then within the next radius
        while no town contains the coordinate. Land parcel maps are added only for the
        municipalities of the containing towns.

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
            Towns first, then land parcels; empty when no shape contains the coordinate.
        """
        if self._supplier is not None:
            self._ensure_areas_at(
                self._supplier, coordinate, crs, is_parcel_included=is_parcel_included
            )
        return self._area_finder.list_at(coordinate, crs, is_parcel_included=is_parcel_included)

    def _to_lot_owner(self, code: AddressCode) -> AddressCode:
        if self._street_municipality_codes is None:
            self._street_municipality_codes = self._towns.list_street_municipality_codes()
        if (
            code.machiaza_id is None
            or not code.is_lot
            or code.lg_code not in self._street_municipality_codes
        ):
            return code
        town = self._towns.find_town(code.lg_code, code.machiaza_id)
        if town is None or not town.is_street_direction:
            return code
        oaza = AddressCode(lg_code=code.lg_code, machiaza_id=code.machiaza_id).parent
        if oaza is None or oaza.machiaza_id is None:
            return code
        oaza_town = self._towns.find_town(oaza.lg_code, oaza.machiaza_id)
        if oaza_town is None or not oaza_town.is_registered:
            return code
        return AddressCode(lg_code=oaza.lg_code, machiaza_id=oaza.machiaza_id, lot=code.lot)

    def _ensure_lots(self, code: AddressCode) -> None:
        if self._supplier is not None and code.is_lot:
            self._supplier.ensure_lots([code.lg_code])

    def _ensure_areas_at(
        self,
        supplier: DatasetSupplier,
        coordinate: GeoCoordinate,
        crs: GeodeticCrs,
        *,
        is_parcel_included: bool,
    ) -> None:
        towns: list[AddressArea] = []
        for radius_meters in self.NEARBY_AREA_RADII_METERS:
            supplier.ensure_areas(
                self._nearest_finder.list_nearby_municipalities(coordinate, crs, radius_meters),
                is_parcel_included=False,
            )
            if self._areas.is_area_imported:
                towns = self._area_finder.list_at(coordinate, crs, is_parcel_included=False)
            if towns:
                break
        if is_parcel_included:
            supplier.ensure_areas({town.code.lg_code for town in towns}, is_parcel_included=True)
