from typing import Protocol

from geo_coordinate import GeoCoordinate

from address_codec_jp.address import AddressCode
from address_codec_jp.frontends.query.options import QueryOptions
from address_codec_jp.results import AddressArea, NearestAddress


class QueryGuard(Protocol):
    """
    Dataset checks a front end applies while ``QueryRunner`` answers a query.

    The runner calls the ``require_*`` methods before or after it reads the datasets
    they name, so that a front end can reject data it does not hold.
    """

    def require_lots(self, code: AddressCode) -> None:
        """
        Check a code before its lots are looked up.

        Parameters
        ----------
        code : AddressCode
            Code to verify or locate; codes without lot numbers need no lots.
        """
        ...

    def require_area(self, code: AddressCode) -> None:
        """
        Check a code before its shape is looked up.

        Parameters
        ----------
        code : AddressCode
            Code whose town boundary or land parcel is found.
        """
        ...

    def require_nearby_lots(
        self, coordinate: GeoCoordinate, options: QueryOptions, nearest: NearestAddress | None
    ) -> None:
        """
        Check the lots that could compete with the nearest address of a coordinate.

        Parameters
        ----------
        coordinate : GeoCoordinate
            Coordinate of the query.
        options : QueryOptions
            Datum and largest distance of the query.
        nearest : NearestAddress | None
            Nearest address found, or ``None`` when none lies within the distance.
        """
        ...

    def require_areas_at(self, areas: list[AddressArea], *, is_parcel_included: bool) -> None:
        """
        Check the shapes found at a coordinate.

        Parameters
        ----------
        areas : list[AddressArea]
            Towns, then land parcels, that contain the coordinate.
        is_parcel_included : bool
            Whether land parcels were looked up.
        """
        ...
