from dataclasses import dataclass
from datetime import datetime

from address_codec_jp.datasets.address_base_registry import AbrDataset


@dataclass(frozen=True, slots=True)
class DatasetImport:
    """
    Record of one registry file imported into a database.

    Parameters
    ----------
    dataset : AbrDataset
        Dataset of the file.
    source_name : str
        File name of the imported file, without its directory.
    source_sha256 : str
        Hexadecimal SHA-256 digest of the file, which identifies the registry release.
    imported_at : datetime
        Time of the import in UTC.
    row_count : int
        Rows stored by the import.

    Raises
    ------
    ValueError
        If ``imported_at`` has no time zone or the digest is malformed.
    """

    dataset: AbrDataset
    source_name: str
    source_sha256: str
    imported_at: datetime
    row_count: int

    def __post_init__(self) -> None:
        if self.imported_at.tzinfo is None:
            raise ValueError("imported_at must have a time zone.")
        if len(self.source_sha256) != 64 or not all(
            character in "0123456789abcdef" for character in self.source_sha256
        ):
            raise ValueError(f"Malformed SHA-256 digest: {self.source_sha256!r}.")
