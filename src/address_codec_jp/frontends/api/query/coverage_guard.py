from typing import override

from geo_coordinate import GeoCoordinate

from address_codec_jp.address import AddressCode
from address_codec_jp.address_codec import AddressCodec
from address_codec_jp.frontends.api.dataset_coverage import DatasetCoverage
from address_codec_jp.frontends.query import QueryGuard, QueryOptions
from address_codec_jp.results import AddressArea, NearestAddress


class CoverageGuard(QueryGuard):
    """
    Guard of web API queries that enforces the coverage of the cache.

    A query that needs the lots, boundaries, or registry maps of a municipality that the
    cache does not hold fails with ``DatasetNotImportedError`` instead of silently
    falling back to an enclosing area or a farther address, because the service never
    downloads them on use. A nearest address requires the lots of every municipality
    that ``list_nearby_municipalities`` gives for its distance, or for the largest
    distance when no lot is that near, since any of them might hold a nearer lot.

    Parameters
    ----------
    codec : AddressCodec
        Codec of the current thread.
    coverage : DatasetCoverage
        Municipalities the cache holds.
    """

    def __init__(self, codec: AddressCodec, coverage: DatasetCoverage) -> None:
        self._codec: AddressCodec = codec
        self._coverage: DatasetCoverage = coverage

    @override
    def require_lots(self, code: AddressCode) -> None:
        """
        Reject a lot code of a municipality whose lots are not prepared.

        Parameters
        ----------
        code : AddressCode
            Code to verify or locate.

        Raises
        ------
        DatasetNotImportedError
            If the lots of the municipality are missing.
        """
        if code.is_lot:
            self._coverage.require_lots(code.lg_code)

    @override
    def require_area(self, code: AddressCode) -> None:
        """
        Reject a code of a municipality whose shapes are not prepared.

        Parameters
        ----------
        code : AddressCode
            Code whose town boundary or land parcel is found.

        Raises
        ------
        DatasetNotImportedError
            If the town boundaries, or the registry maps a land parcel needs, are missing.
        """
        self._coverage.require_boundaries(code.lg_code)
        if self._codec.has_parcel_shape(code):
            self._coverage.require_parcel_maps(code.lg_code)

    @override
    def require_nearby_lots(
        self, coordinate: GeoCoordinate, options: QueryOptions, nearest: NearestAddress | None
    ) -> None:
        """
        Reject a coordinate near municipalities whose lots are not prepared.

        Parameters
        ----------
        coordinate : GeoCoordinate
            Coordinate of the query.
        options : QueryOptions
            Datum and largest distance of the query.
        nearest : NearestAddress | None
            Nearest address found, or ``None`` when none lies within the distance.

        Raises
        ------
        DatasetNotImportedError
            If a municipality that might hold a nearer lot is missing.
        """
        competing_distance_meters = (
            min(nearest.distance_meters, options.max_distance_meters)
            if nearest is not None and nearest.code.is_lot
            else options.max_distance_meters
        )
        if competing_distance_meters <= 0:
            return
        nearby_codes = self._codec.list_nearby_municipalities(
            coordinate, options.crs, competing_distance_meters
        )
        for lg_code in sorted(nearby_codes):
            self._coverage.require_lots(lg_code)

    @override
    def require_areas_at(self, areas: list[AddressArea], *, is_parcel_included: bool) -> None:
        """
        Reject shapes of municipalities whose boundaries or maps are not prepared.

        Parameters
        ----------
        areas : list[AddressArea]
            Towns, then land parcels, that contain the coordinate.
        is_parcel_included : bool
            Whether land parcels were looked up.

        Raises
        ------
        DatasetNotImportedError
            If the town boundaries, or the registry maps when parcels are included, of a
            containing municipality are missing.
        """
        for lg_code in sorted({area.code.lg_code for area in areas}):
            self._coverage.require_boundaries(lg_code)
            if is_parcel_included:
                self._coverage.require_parcel_maps(lg_code)
