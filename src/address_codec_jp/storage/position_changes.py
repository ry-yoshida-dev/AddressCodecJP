from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PositionChanges:
    """
    Counts of rows changed by storing position records.

    Parameters
    ----------
    stored_count : int
        Points and lot numbers stored or replaced.
    removed_count : int
        Previously stored lot numbers removed because the registry marks them abolished.
    """

    stored_count: int
    removed_count: int
