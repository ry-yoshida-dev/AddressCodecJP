from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ImportSummary:
    """
    Counts of towns stored by an import.

    Parameters
    ----------
    registered_count : int
        Towns read from the registry.
    complemented_count : int
        Oaza-level towns added for oaza that the registry lists only by chome.
    """

    registered_count: int
    complemented_count: int
