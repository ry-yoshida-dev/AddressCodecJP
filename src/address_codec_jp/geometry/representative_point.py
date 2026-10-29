from dataclasses import dataclass

from geo_coordinate import GeodeticCrs


@dataclass(frozen=True, slots=True)
class RepresentativePoint:
    """
    Representative point of an area as published by the Address Base Registry.

    Parameters
    ----------
    longitude : float
        Longitude in decimal degrees.
    latitude : float
        Latitude in decimal degrees.
    crs : GeodeticCrs
        Datum the point is measured on. The registry mixes JGD2000 and JGD2011.

    Raises
    ------
    ValueError
        If the longitude or latitude is out of range.
    """

    longitude: float
    latitude: float
    crs: GeodeticCrs

    def __post_init__(self) -> None:
        if not -180.0 <= self.longitude <= 180.0:
            raise ValueError(f"Longitude must be within [-180, 180], got {self.longitude}.")
        if not -90.0 <= self.latitude <= 90.0:
            raise ValueError(f"Latitude must be within [-90, 90], got {self.latitude}.")
