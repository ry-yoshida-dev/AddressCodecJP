from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CacheStatus:
    """
    Contents of the database of a ``DatabaseCache``.

    Parameters
    ----------
    path : Path
        Path of the database.
    is_built : bool
        Whether the database exists.
    size_bytes : int
        Size of the database file, zero when it is not built.
    built_at : datetime | None
        Time of the first import in UTC, or ``None`` when the database is not built.
    registry_file_count : int
        Registry files imported.
    lot_municipality_codes : tuple[str, ...]
        Municipalities whose blocks, residences, or land parcels were added.
    boundary_municipality_codes : tuple[str, ...]
        Municipalities whose census town boundaries were added.
    parcel_map_municipality_codes : tuple[str, ...]
        Municipalities whose registry maps were added.
    obsolete_paths : tuple[Path, ...]
        Databases of other schema versions and leftovers of interrupted builds.
    """

    path: Path
    is_built: bool
    size_bytes: int
    built_at: datetime | None
    registry_file_count: int
    lot_municipality_codes: tuple[str, ...]
    boundary_municipality_codes: tuple[str, ...]
    parcel_map_municipality_codes: tuple[str, ...]
    obsolete_paths: tuple[Path, ...]
