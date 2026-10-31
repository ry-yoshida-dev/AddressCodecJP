from address_codec_jp.address import Address, AddressCode
from address_codec_jp.address_codec import AddressCodec
from address_codec_jp.frontends.serialization.json_value import JsonValue
from address_codec_jp.frontends.serialization.rendered_address import RenderedAddress
from address_codec_jp.results import (
    AddressArea,
    AddressLocation,
    AddressMatch,
    AreaSource,
    NearestAddress,
)
from address_codec_jp.text.formatting import AddressFormat, LotStyle


class ResultSerializer:
    """
    Converter of codec results to JSON-compatible fields.

    The command line and the web API write their results through this class, so both
    give the same fields. Points and shapes tell with ``is_exact`` whether they stand
    for the requested address itself or for an enclosing area.

    Parameters
    ----------
    codec : AddressCodec
        Codec that renders the addresses of codes and areas.
    """

    def __init__(self, codec: AddressCodec) -> None:
        self._codec: AddressCodec = codec

    def match(self, address_match: AddressMatch) -> dict[str, JsonValue]:
        """
        Describe an interpreted address.

        Parameters
        ----------
        address_match : AddressMatch
            Result of ``AddressCodec.match``.

        Returns
        -------
        dict[str, JsonValue]
            ``code``, ``level``, ``remainder``, and ``town_name_tier``.
        """
        tier = address_match.town_name_tier
        return {
            "code": str(address_match.code),
            "level": address_match.code.level.name,
            "remainder": address_match.remainder,
            "town_name_tier": None if tier is None else tier.name,
        }

    def render(
        self, code: AddressCode, address_format: AddressFormat = AddressCodec.DEFAULT_FORMAT
    ) -> RenderedAddress:
        """
        Render the address of a code.

        Parameters
        ----------
        code : AddressCode
            Address code.
        address_format : AddressFormat
            Output format of the address.

        Returns
        -------
        RenderedAddress
            The code with its address.

        Raises
        ------
        AddressNotFoundError
            If the area of the code is not registered.
        ReadingNotFoundError
            If katakana is requested and the registry has no reading of a name.
        """
        return RenderedAddress(code, self._codec.decode(code, address_format))

    def render_all(
        self, addresses: list[Address], address_format: AddressFormat
    ) -> list[RenderedAddress]:
        """
        Render the addresses of a listing.

        Parameters
        ----------
        addresses : list[Address]
            Result of ``AddressCodec.list_by_postal_code``, ``list_children``, or
            ``list_by_name``.
        address_format : AddressFormat
            Output format of the addresses.

        Returns
        -------
        list[RenderedAddress]
            Each code with its address, in the order of ``addresses``.

        Raises
        ------
        ReadingNotFoundError
            If katakana is requested and the registry has no reading of a name.
        """
        return [self.render(address.code, address_format) for address in addresses]

    def decoded(self, rendered: RenderedAddress) -> dict[str, JsonValue]:
        """
        Describe the address of a code.

        Parameters
        ----------
        rendered : RenderedAddress
            Result of ``render``.

        Returns
        -------
        dict[str, JsonValue]
            ``code`` in canonical form and ``address``.
        """
        return {"code": str(rendered.code), "address": rendered.address}

    def location(self, location: AddressLocation) -> dict[str, JsonValue]:
        """
        Describe a representative point.

        Parameters
        ----------
        location : AddressLocation
            Result of ``AddressCodec.locate``.

        Returns
        -------
        dict[str, JsonValue]
            ``code``, ``located_code``, ``level``, ``is_exact``, ``latitude``,
            ``longitude``, and ``crs``.
        """
        return {
            "code": str(location.code),
            "located_code": str(location.located_code),
            "level": location.level.name,
            "is_exact": location.is_exact,
            "latitude": location.latitude_degrees,
            "longitude": location.longitude_degrees,
            "crs": str(location.crs),
        }

    def nearest(self, nearest: NearestAddress, address: str) -> dict[str, JsonValue]:
        """
        Describe the nearest address.

        Parameters
        ----------
        nearest : NearestAddress
            Result of ``AddressCodec.find_nearest``.
        address : str
            Address rendered from ``nearest.code``.

        Returns
        -------
        dict[str, JsonValue]
            ``code``, ``address``, ``level``, ``latitude``, ``longitude``,
            ``distance_meters``, and ``crs``.
        """
        location = nearest.location
        return {
            "code": str(nearest.code),
            "address": address,
            "level": location.level.name,
            "latitude": location.latitude_degrees,
            "longitude": location.longitude_degrees,
            "distance_meters": nearest.distance_meters,
            "crs": str(location.crs),
        }

    def towns(self, towns: list[RenderedAddress]) -> list[JsonValue]:
        """
        Describe each town of a postal code by its code and address.

        Parameters
        ----------
        towns : list[RenderedAddress]
            Towns of the postal code, from ``render_all``.

        Returns
        -------
        list[JsonValue]
            ``code`` and ``address`` of each town.
        """
        return [{"code": str(town.code), "address": town.address} for town in towns]

    def listed_areas(self, areas: list[RenderedAddress]) -> list[JsonValue]:
        """
        Describe each listed area by its code, address, and level.

        Parameters
        ----------
        areas : list[RenderedAddress]
            Children or named areas, from ``render_all``.

        Returns
        -------
        list[JsonValue]
            ``code``, ``address``, and ``level`` of each area.
        """
        return [
            {"code": str(area.code), "address": area.address, "level": area.code.level.name}
            for area in areas
        ]

    def area(self, area: AddressArea, *, is_geometry_included: bool) -> dict[str, JsonValue]:
        """
        Describe the shape of an address.

        Parameters
        ----------
        area : AddressArea
            Result of ``AddressCodec.find_area``.
        is_geometry_included : bool
            Whether the GeoJSON geometry is written.

        Returns
        -------
        dict[str, JsonValue]
            ``code``, ``located_code``, ``level``, ``is_exact``, ``sources``, and
            optionally ``geometry``.
        """
        fields: dict[str, JsonValue] = {
            "code": str(area.code),
            "located_code": str(area.located_code),
            "level": area.level.name,
            "is_exact": area.is_exact,
            "sources": self.source_names(area),
        }
        if is_geometry_included:
            fields["geometry"] = area.shape.to_geojson_geometry()
        return fields

    def areas(self, areas: list[AddressArea], *, is_geometry_included: bool) -> list[JsonValue]:
        """
        Describe the shapes that contain a coordinate.

        Parameters
        ----------
        areas : list[AddressArea]
            Result of ``AddressCodec.find_areas_at``.
        is_geometry_included : bool
            Whether the GeoJSON geometries are written.

        Returns
        -------
        list[JsonValue]
            ``code``, ``address``, ``level``, ``sources``, and optionally ``geometry`` of
            each area.
        """
        values: list[JsonValue] = []
        for area in areas:
            fields: dict[str, JsonValue] = {
                "code": str(area.code),
                "address": self.area_address(area),
                "level": area.level.name,
                "sources": self.source_names(area),
            }
            if is_geometry_included:
                fields["geometry"] = area.shape.to_geojson_geometry()
            values.append(fields)
        return values

    def area_address(self, area: AddressArea) -> str:
        """
        Render the address of an area, land parcels in parcel notation.

        Parameters
        ----------
        area : AddressArea
            Area to render.

        Returns
        -------
        str
            Address of ``area.code``.
        """
        is_parcel = AreaSource.REGISTRY_MAP in area.sources
        lot_style = LotStyle.LAND_PARCEL if is_parcel else LotStyle.AUTOMATIC
        return self._codec.decode(area.code, AddressFormat(lot_style=lot_style))

    def source_names(self, area: AddressArea) -> str:
        """
        List the datasets of an area.

        Parameters
        ----------
        area : AddressArea
            Area to describe.

        Returns
        -------
        str
            Comma-separated ``AreaSource`` values in alphabetical order.
        """
        return ",".join(sorted(source.value for source in area.sources))
