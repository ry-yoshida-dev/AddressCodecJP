from address_codec_jp.address_codec import AddressCodec
from address_codec_jp.domain.address import Address
from address_codec_jp.domain.address_area import AddressArea
from address_codec_jp.domain.address_location import AddressLocation
from address_codec_jp.domain.address_match import AddressMatch
from address_codec_jp.domain.area_source import AreaSource
from address_codec_jp.domain.nearest_address import NearestAddress
from address_codec_jp.formatting.address_format import AddressFormat
from address_codec_jp.formatting.lot_style import LotStyle
from address_codec_jp.serialization.json_value import JsonValue


class ResultSerializer:
    """
    Converter of codec results to JSON-compatible fields.

    The command line and the web API write their results through this class, so both
    give the same fields. Points and shapes tell with ``is_exact`` whether they stand
    for the requested address itself or for an enclosing area.

    Parameters
    ----------
    codec : AddressCodec
        Codec that renders the addresses of nearest points and listed areas.
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

    def decoded(self, code: str, address_format: AddressFormat) -> dict[str, JsonValue]:
        """
        Describe the address of a code.

        Parameters
        ----------
        code : str
            Address code.
        address_format : AddressFormat
            Output format of the address.

        Returns
        -------
        dict[str, JsonValue]
            ``address``.

        Raises
        ------
        ValueError
            If the code is malformed.
        AddressNotFoundError
            If the area of the code is not registered.
        ReadingNotFoundError
            If katakana is requested and the registry has no reading of a name.
        """
        return {"address": self._codec.decode(code, address_format)}

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

    def nearest(self, nearest: NearestAddress) -> dict[str, JsonValue]:
        """
        Describe the nearest address.

        Parameters
        ----------
        nearest : NearestAddress
            Result of ``AddressCodec.find_nearest``.

        Returns
        -------
        dict[str, JsonValue]
            ``code``, ``address``, ``level``, ``latitude``, ``longitude``,
            ``distance_meters``, and ``crs``.
        """
        location = nearest.location
        return {
            "code": str(nearest.code),
            "address": self._codec.decode(nearest.code),
            "level": location.level.name,
            "latitude": location.latitude_degrees,
            "longitude": location.longitude_degrees,
            "distance_meters": nearest.distance_meters,
            "crs": str(location.crs),
        }

    def towns(
        self, addresses: list[Address], address_format: AddressFormat
    ) -> dict[str, JsonValue]:
        """
        Describe the towns of a postal code.

        Parameters
        ----------
        addresses : list[Address]
            Result of ``AddressCodec.list_by_postal_code``.
        address_format : AddressFormat
            Output format of the addresses.

        Returns
        -------
        dict[str, JsonValue]
            ``towns``, each with its ``code`` and ``address``.

        Raises
        ------
        ReadingNotFoundError
            If katakana is requested and the registry has no reading of a name.
        """
        towns: list[JsonValue] = [
            {
                "code": str(address.code),
                "address": self._codec.decode(address.code, address_format),
            }
            for address in addresses
        ]
        return {"towns": towns}

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

    def areas(
        self, areas: list[AddressArea], *, is_geometry_included: bool
    ) -> dict[str, JsonValue]:
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
        dict[str, JsonValue]
            ``areas``, each with its ``code``, ``address``, ``level``, ``sources``, and
            optionally ``geometry``.
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
        return {"areas": values}

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
