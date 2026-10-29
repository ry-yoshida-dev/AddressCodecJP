import math
from collections.abc import Callable
from typing import ClassVar

from geo_coordinate import GeoCoordinate, GeodeticCrs

from address_codec_jp.domain.address_location import AddressLocation
from address_codec_jp.domain.address_point import AddressPoint
from address_codec_jp.domain.coordinate_bounds import CoordinateBounds
from address_codec_jp.domain.nearest_address import NearestAddress
from address_codec_jp.errors.dataset_not_imported_error import DatasetNotImportedError
from address_codec_jp.errors.position_not_found_error import PositionNotFoundError
from address_codec_jp.positioning.datum_converter import DatumConverter
from address_codec_jp.storage.position_repository import PositionRepository


class NearestAddressFinder:
    """
    Finder of the address whose representative point is nearest to a coordinate.

    Blocks, residences, and parcels are searched first, then towns. Each is searched in
    squares that grow from ``INITIAL_RADIUS_METERS`` until a point lies within the
    inscribed circle or the maximum distance is reached. Points are ranked on their
    published datum, which differs from JGD2011 by centimeters except near the 2011
    Tohoku earthquake; the reported distance uses the transformed point.

    Parameters
    ----------
    repository : PositionRepository
        Imported representative points.
    """

    INITIAL_RADIUS_METERS: ClassVar[float] = 50.0
    _RADIUS_GROWTH: ClassVar[float] = 4.0
    _SEARCH_DATUM: ClassVar[GeodeticCrs] = GeodeticCrs.JGD2011
    _MINIMUM_METERS_PER_DEGREE: ClassVar[float] = 110_000.0

    def __init__(self, repository: PositionRepository) -> None:
        self._repository: PositionRepository = repository
        self._converter: DatumConverter = DatumConverter()

    def find(
        self, coordinate: GeoCoordinate, crs: GeodeticCrs, max_distance_meters: float
    ) -> NearestAddress:
        """
        Find the address nearest to a coordinate.

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
            Nearest block, residence, or parcel, or the nearest town when no lot point
            is within the distance.

        Raises
        ------
        ValueError
            If ``max_distance_meters`` is not positive.
        PositionNotFoundError
            If no point is within ``max_distance_meters``.
        DatasetNotImportedError
            If no position has been imported.
        RuntimeError
            If ``crs`` cannot be transformed.
        """
        if not max_distance_meters > 0:
            raise ValueError(f"max_distance_meters must be positive, got {max_distance_meters}.")
        if not self._repository.is_position_imported:
            raise DatasetNotImportedError(
                "No positions have been imported. Import position datasets."
            )
        searched = self._converter.transform(coordinate, crs, self._SEARCH_DATUM)
        searches: list[Callable[[CoordinateBounds], list[AddressPoint]]] = [
            self._repository.list_lot_points,
            self._repository.list_town_points,
        ]
        for search in searches:
            nearest = self._find_nearest(searched, search, max_distance_meters)
            if nearest is not None:
                return self._to_nearest_address(searched, nearest, crs)
        raise PositionNotFoundError(f"No address is imported within {max_distance_meters} m.")

    def _find_nearest(
        self,
        searched: GeoCoordinate,
        search: Callable[[CoordinateBounds], list[AddressPoint]],
        max_distance_meters: float,
    ) -> AddressPoint | None:
        radius_meters = min(self.INITIAL_RADIUS_METERS, max_distance_meters)
        while True:
            candidates = search(self._bounds(searched, radius_meters))
            if candidates:
                nearest = min(candidates, key=lambda item: self._distance(searched, item))
                if self._distance(searched, nearest) <= radius_meters:
                    return nearest
            if radius_meters >= max_distance_meters:
                return None
            radius_meters = min(radius_meters * self._RADIUS_GROWTH, max_distance_meters)

    def _bounds(self, center: GeoCoordinate, radius_meters: float) -> CoordinateBounds:
        latitude = self._latitude_degrees(center)
        longitude = self._longitude_degrees(center)
        latitude_margin = radius_meters / self._MINIMUM_METERS_PER_DEGREE
        widest_latitude = min(abs(latitude) + latitude_margin, 89.0)
        longitude_margin = latitude_margin / math.cos(math.radians(widest_latitude))
        return CoordinateBounds(
            south_degrees=latitude - latitude_margin,
            north_degrees=latitude + latitude_margin,
            west_degrees=longitude - longitude_margin,
            east_degrees=longitude + longitude_margin,
        )

    def _distance(self, searched: GeoCoordinate, candidate: AddressPoint) -> float:
        point = GeoCoordinate.from_degrees(candidate.point.latitude, candidate.point.longitude)
        return float(searched.distance_to(point).meter.flat[0])

    def _to_nearest_address(
        self, searched: GeoCoordinate, nearest: AddressPoint, crs: GeodeticCrs
    ) -> NearestAddress:
        on_search_datum = self._converter.to_coordinate(nearest.point, self._SEARCH_DATUM)
        return NearestAddress(
            location=AddressLocation(
                code=nearest.code,
                located_code=nearest.code,
                coordinate=self._converter.to_coordinate(nearest.point, crs),
                crs=crs,
            ),
            distance_meters=float(searched.distance_to(on_search_datum).meter.flat[0]),
        )

    def _latitude_degrees(self, coordinate: GeoCoordinate) -> float:
        return float(coordinate.latitude.degree.flat[0])

    def _longitude_degrees(self, coordinate: GeoCoordinate) -> float:
        return float(coordinate.longitude.degree.flat[0])
