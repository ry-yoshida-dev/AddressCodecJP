from address_codec_jp.frontends.serialization.rendered_address import RenderedAddress
from address_codec_jp.frontends.serialization.result_serializer import ResultSerializer
from address_codec_jp.results import AddressArea, AddressLocation, AddressMatch, NearestAddress


class ResultRows:
    """
    Converter of codec results to the tab-separated rows of the command line.

    Each row lists the values of one result line without the input, which the writer
    puts first. Addresses come as ``RenderedAddress`` from ``ResultSerializer.render``, so
    that the rows and the JSON fields share one rendering.

    Parameters
    ----------
    serializer : ResultSerializer
        Serializer that renders the addresses and sources of areas.
    """

    def __init__(self, serializer: ResultSerializer) -> None:
        self._serializer: ResultSerializer = serializer

    def match(self, address_match: AddressMatch) -> list[list[str]]:
        """
        Write an interpreted address.

        Parameters
        ----------
        address_match : AddressMatch
            Result of ``AddressCodec.match``.

        Returns
        -------
        list[list[str]]
            The code, followed by the unparsed remainder when there is one.
        """
        code = str(address_match.code)
        if address_match.remainder:
            return [[code, address_match.remainder]]
        return [[code]]

    def address(self, rendered: RenderedAddress) -> list[list[str]]:
        """
        Write a decoded address.

        Parameters
        ----------
        rendered : RenderedAddress
            Result of ``ResultSerializer.render``.

        Returns
        -------
        list[list[str]]
            The address alone.
        """
        return [[rendered.address]]

    def location(self, location: AddressLocation) -> list[list[str]]:
        """
        Write a representative point.

        Parameters
        ----------
        location : AddressLocation
            Result of ``AddressCodec.locate``.

        Returns
        -------
        list[list[str]]
            Code, located code, level, latitude, longitude, and datum.
        """
        return [
            [
                str(location.code),
                str(location.located_code),
                location.level.name,
                f"{location.latitude_degrees:.9f}",
                f"{location.longitude_degrees:.9f}",
                str(location.crs),
            ]
        ]

    def nearest(self, nearest: NearestAddress, address: str) -> list[list[str]]:
        """
        Write the nearest address.

        Parameters
        ----------
        nearest : NearestAddress
            Result of ``AddressCodec.find_nearest``.
        address : str
            Address rendered from ``nearest.code``.

        Returns
        -------
        list[list[str]]
            Code, address, level, latitude, longitude, distance in meters, and datum.
        """
        location = nearest.location
        return [
            [
                str(nearest.code),
                address,
                location.level.name,
                f"{location.latitude_degrees:.9f}",
                f"{location.longitude_degrees:.9f}",
                f"{nearest.distance_meters:.1f}",
                str(location.crs),
            ]
        ]

    def towns(self, towns: list[RenderedAddress]) -> list[list[str]]:
        """
        Write the towns of a postal code.

        Parameters
        ----------
        towns : list[RenderedAddress]
            Towns of the postal code, from ``ResultSerializer.render_all``.

        Returns
        -------
        list[list[str]]
            Code and address of each town.
        """
        return [[str(town.code), town.address] for town in towns]

    def listed_areas(self, areas: list[RenderedAddress]) -> list[list[str]]:
        """
        Write listed areas.

        Parameters
        ----------
        areas : list[RenderedAddress]
            Children or named areas, from ``ResultSerializer.render_all``.

        Returns
        -------
        list[list[str]]
            Code, address, and level of each area.
        """
        return [[str(area.code), area.address, area.code.level.name] for area in areas]

    def area(self, area: AddressArea, *, is_geometry_included: bool) -> list[list[str]]:
        """
        Write the shape of an address.

        Parameters
        ----------
        area : AddressArea
            Result of ``AddressCodec.find_area``.
        is_geometry_included : bool
            Whether the GeoJSON geometry is written.

        Returns
        -------
        list[list[str]]
            Code, located code, level, sources, and optionally the geometry.
        """
        return [
            [
                str(area.code),
                str(area.located_code),
                area.level.name,
                self._serializer.source_names(area),
                *([area.shape.to_geojson()] if is_geometry_included else []),
            ]
        ]

    def areas(self, areas: list[AddressArea], *, is_geometry_included: bool) -> list[list[str]]:
        """
        Write the shapes that contain a coordinate.

        Parameters
        ----------
        areas : list[AddressArea]
            Result of ``AddressCodec.find_areas_at``.
        is_geometry_included : bool
            Whether the GeoJSON geometries are written.

        Returns
        -------
        list[list[str]]
            Code, address, level, sources, and optionally the geometry of each area.
        """
        return [
            [
                str(area.code),
                self._serializer.area_address(area),
                area.level.name,
                self._serializer.source_names(area),
                *([area.shape.to_geojson()] if is_geometry_included else []),
            ]
            for area in areas
        ]
