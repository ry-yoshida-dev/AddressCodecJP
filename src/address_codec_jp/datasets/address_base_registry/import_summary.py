from dataclasses import dataclass
from pathlib import Path

from address_codec_jp.datasets.address_base_registry.abr_dataset import AbrDataset


@dataclass(frozen=True, slots=True)
class ImportSummary:
    """
    Result of importing one registry file.

    Parameters
    ----------
    source : Path
        Imported file.
    dataset : AbrDataset
        Dataset of the imported file.
    stored_count : int
        Rows stored. For the town master, towns read from the registry; for other
        datasets, points and lot numbers stored or replaced. Lot numbers that address
        codes cannot express are skipped.
    removed_count : int
        Previously imported rows removed. For the town master, points and lot numbers
        of towns no longer in the master; for number masters, lots marked abolished.
    complemented_count : int
        Oaza-level towns added for oaza that the registry lists only by chome. Always
        ``0`` for datasets other than the town master.
    """

    source: Path
    dataset: AbrDataset
    stored_count: int
    removed_count: int
    complemented_count: int = 0
