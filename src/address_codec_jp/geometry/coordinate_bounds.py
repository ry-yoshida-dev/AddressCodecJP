from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CoordinateBounds:
    """
    Latitude and longitude range of a rectangular search area.

    Parameters
    ----------
    south_degrees : float
        Smallest latitude in decimal degrees.
    north_degrees : float
        Largest latitude in decimal degrees.
    west_degrees : float
        Smallest longitude in decimal degrees.
    east_degrees : float
        Largest longitude in decimal degrees.

    Raises
    ------
    ValueError
        If a minimum exceeds its maximum.
    """

    south_degrees: float
    north_degrees: float
    west_degrees: float
    east_degrees: float

    def __post_init__(self) -> None:
        if self.south_degrees > self.north_degrees:
            raise ValueError("south_degrees must not exceed north_degrees.")
        if self.west_degrees > self.east_degrees:
            raise ValueError("west_degrees must not exceed east_degrees.")
