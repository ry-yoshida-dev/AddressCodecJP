from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TownReplacement:
    """
    Counts of towns stored by replacing the town table.

    Parameters
    ----------
    registered_count : int
        Towns read from the registry.
    complemented_count : int
        Oaza-level towns added for oaza that the registry lists only by chome.
    """

    registered_count: int
    complemented_count: int
