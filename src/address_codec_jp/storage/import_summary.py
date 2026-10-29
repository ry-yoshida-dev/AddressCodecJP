from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ImportSummary:
    """
    Counts of an import of the town master.

    Parameters
    ----------
    registered_count : int
        Towns read from the registry.
    complemented_count : int
        Oaza-level towns added for oaza that the registry lists only by chome.
    removed_position_count : int
        Imported points and lot numbers removed because their area is no longer in the
        town master.
    """

    registered_count: int
    complemented_count: int
    removed_position_count: int
