from typing import override

from geo_coordinate import GeoCoordinate

from address_codec_jp.address import AddressCode
from address_codec_jp.frontends.query.guard import QueryGuard
from address_codec_jp.frontends.query.options import QueryOptions
from address_codec_jp.results import AddressArea, NearestAddress


class PassThroughGuard(QueryGuard):
    """
    Guard that admits every dataset.

    The command line uses it, since a codec on the cache adds missing datasets on use,
    and so does the web API when it does not require coverage.
    """

    @override
    def require_lots(self, code: AddressCode) -> None:
        """Admit the code; a codec on the cache adds its lots on use."""
        return

    @override
    def require_area(self, code: AddressCode) -> None:
        """Admit the code; a codec on the cache adds its shapes on use."""
        return

    @override
    def require_nearby_lots(
        self, coordinate: GeoCoordinate, options: QueryOptions, nearest: NearestAddress | None
    ) -> None:
        """Admit the coordinate without checking the lots around it."""
        return

    @override
    def require_areas_at(self, areas: list[AddressArea], *, is_parcel_included: bool) -> None:
        """Admit the shapes found."""
        return
