from dataclasses import dataclass

from address_codec_jp.storage.abr_dataset import AbrDataset


@dataclass(frozen=True, slots=True)
class PositionImportSummary:
    """
    Result of importing one position-related registry file.

    Parameters
    ----------
    dataset : AbrDataset
        Kind of the imported file.
    stored_count : int
        Rows stored. Lot numbers that address codes cannot express are skipped.
    removed_count : int
        Previously imported lot numbers removed because the file marks them abolished.
    """

    dataset: AbrDataset
    stored_count: int
    removed_count: int
