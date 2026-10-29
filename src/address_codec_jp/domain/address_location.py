from dataclasses import dataclass

from geo_coordinate import GeoCoordinate, GeodeticCrs

from address_codec_jp.domain.address_code import AddressCode
from address_codec_jp.domain.position_level import PositionLevel


@dataclass(frozen=True, slots=True)
class AddressLocation:
    """
    Representative point of an address.

    When the registry has no point for the address itself, the point of the nearest
    enclosing area is used, e.g. the block for a residence or the town for a block.

    Parameters
    ----------
    code : AddressCode
        Code of the requested address.
    located_code : AddressCode
        Code of the area whose representative point is returned. Equal to ``code`` or
        one of its ancestors.
    coordinate : GeoCoordinate
        Representative point of ``located_code``.
    crs : GeodeticCrs
        Datum ``coordinate`` is measured on.
    """

    code: AddressCode
    located_code: AddressCode
    coordinate: GeoCoordinate
    crs: GeodeticCrs

    @property
    def latitude_degrees(self) -> float:
        """
        Latitude of the point.

        Returns
        -------
        float
            Latitude in decimal degrees on ``crs``.
        """
        return float(self.coordinate.latitude.degree.flat[0])

    @property
    def longitude_degrees(self) -> float:
        """
        Longitude of the point.

        Returns
        -------
        float
            Longitude in decimal degrees on ``crs``.
        """
        return float(self.coordinate.longitude.degree.flat[0])

    @property
    def level(self) -> PositionLevel:
        """
        Granularity of the returned point.

        Returns
        -------
        PositionLevel
            Level of ``located_code``.
        """
        return PositionLevel.of(self.located_code)

    @property
    def is_exact(self) -> bool:
        """
        Tell whether the point stands for the requested address itself.

        Returns
        -------
        bool
            ``True`` when no enclosing area had to be used.
        """
        return self.located_code == self.code
