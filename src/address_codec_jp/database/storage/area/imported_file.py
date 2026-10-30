from dataclasses import dataclass
from datetime import datetime

from address_codec_jp.results import AreaSource


@dataclass(frozen=True, slots=True)
class AreaImport:
    """
    Record of one area file imported into a database.

    Parameters
    ----------
    source : AreaSource
        Dataset of the file.
    lg_code : str
        Six-digit local government code of the municipality the file covers.
    source_name : str
        File name of the imported file, without its directory.
    source_sha256 : str
        Hexadecimal SHA-256 digest of the file.
    imported_at : datetime
        Time of the import in UTC.
    stored_count : int
        Shapes stored by the import.
    unmatched_count : int
        Shapes skipped because no registered address fits them.

    Raises
    ------
    ValueError
        If ``imported_at`` has no time zone.
    """

    source: AreaSource
    lg_code: str
    source_name: str
    source_sha256: str
    imported_at: datetime
    stored_count: int
    unmatched_count: int

    def __post_init__(self) -> None:
        if self.imported_at.tzinfo is None:
            raise ValueError("imported_at must have a time zone.")
