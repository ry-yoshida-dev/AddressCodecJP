import hashlib
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import ClassVar, Self

from address_codec_jp.database.storage import AddressDatabase, DatasetImport
from address_codec_jp.datasets.address_base_registry import (
    AbrCsvFile,
    AbrDataset,
    AbrPositionCsvReader,
    AbrTownCsvReader,
    ImportSummary,
)


class RegistryImporter:
    """
    Importer of Address Base Registry datasets into an address database.

    The dataset of a file is identified by its CSV header, so files may be renamed. Each
    file is imported in one transaction together with its entry in the import log, so
    that a failed import leaves the database as it was, and ``AddressCodec.list_imports``
    tells exactly which registry files the database holds.

    Parameters
    ----------
    database : AddressDatabase
        Writable database. It is closed by ``close``.

    Raises
    ------
    ValueError
        If the database was opened read-only.

    Examples
    --------
    >>> with RegistryImporter.open("towns.sqlite3") as importer:  # doctest: +SKIP
    ...     summaries = importer.import_files(sorted(Path("data").glob("*.zip")))
    """

    _HASH_CHUNK_SIZE: ClassVar[int] = 1 << 20

    def __init__(self, database: AddressDatabase) -> None:
        if not database.is_writable:
            raise ValueError("RegistryImporter requires a database opened for writing.")
        self._database: AddressDatabase = database

    @classmethod
    def open(cls, database_path: Path | str) -> Self:
        """
        Open an importer on a database, creating the file if needed.

        Parameters
        ----------
        database_path : Path | str
            SQLite file path, or ``":memory:"`` for an in-memory database.

        Returns
        -------
        Self
            Importer bound to the database.

        Raises
        ------
        UnsupportedDatabaseError
            If the file exists but is not a database of this version of the library.
        """
        return cls(AddressDatabase.open_writable(database_path))

    @property
    def database(self) -> AddressDatabase:
        """
        Database the datasets are imported into.

        Returns
        -------
        AddressDatabase
            Writable database, e.g. to build an ``AddressCodec`` on an in-memory database.
        """
        return self._database

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying database."""
        self._database.close()

    def import_files(self, paths: Sequence[Path]) -> list[ImportSummary]:
        """
        Import several registry files, the town master first.

        Every file is identified before the first import, so that a missing or unknown
        file is reported before anything changes. Each file is then imported in a
        transaction of its own.

        Parameters
        ----------
        paths : Sequence[Path]
            Registry CSV files or their ZIP archives, in any order. A path given twice
            is imported once.

        Returns
        -------
        list[ImportSummary]
            Summaries in the order the files were imported: town masters first, then the
            other files in the given order.

        Raises
        ------
        FileNotFoundError
            If a file does not exist.
        RegistryFormatError
            If a file is not a registry dataset or is malformed. Files imported before
            the malformed one are kept.
        """
        datasets = {path: AbrCsvFile(path).detect_dataset() for path in paths}
        ordered_paths = sorted(datasets, key=lambda path: datasets[path].is_position_related)
        return [self._import(path, datasets[path]) for path in ordered_paths]

    def import_file(self, path: Path) -> ImportSummary:
        """
        Import one registry file.

        The town master replaces the towns of the previous import; towns that are not in
        the new master are removed together with their imported points and lot numbers.
        Oaza-level towns are added for oaza registered only by chome, so that addresses
        ending at the oaza, such as ``台東区浅草橋``, can be encoded. Abolished rows are
        skipped.

        Other datasets add points and lot numbers. A lot is located only when both its
        number master and its position extension are imported, in any order. Rows with
        the same identifiers as earlier imports are replaced, and lots that a number
        master marks abolished are removed.

        Parameters
        ----------
        path : Path
            Registry CSV file or its ZIP archive, e.g. ``mt_town_all.csv.zip`` or
            ``mt_town_pos_pref13.csv.zip``.

        Returns
        -------
        ImportSummary
            Dataset of the file and numbers of stored, removed, and added rows.

        Raises
        ------
        FileNotFoundError
            If the file does not exist.
        RegistryFormatError
            If the file is not a registry dataset or is malformed. The previous contents
            are kept in that case.
        """
        return self._import(path, AbrCsvFile(path).detect_dataset())

    def _import(self, path: Path, dataset: AbrDataset) -> ImportSummary:
        digest = self._digest(path)
        with self._database.transaction():
            summary = self._store(path, dataset)
            self._database.imports.add(
                DatasetImport(
                    dataset=dataset,
                    source_name=path.name,
                    source_sha256=digest,
                    imported_at=datetime.now(UTC),
                    row_count=summary.stored_count,
                )
            )
        return summary

    def _store(self, path: Path, dataset: AbrDataset) -> ImportSummary:
        match dataset:
            case AbrDataset.TOWN:
                replacement = self._database.towns.replace_all(AbrTownCsvReader().read(path))
                return ImportSummary(
                    source=path,
                    dataset=dataset,
                    stored_count=replacement.registered_count,
                    removed_count=self._database.positions.remove_orphans(),
                    complemented_count=replacement.complemented_count,
                )
            case _:
                changes = self._database.positions.save_all(AbrPositionCsvReader().read(path))
                return ImportSummary(
                    source=path,
                    dataset=dataset,
                    stored_count=changes.stored_count,
                    removed_count=changes.removed_count,
                )

    def _digest(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            while chunk := stream.read(self._HASH_CHUNK_SIZE):
                digest.update(chunk)
        return digest.hexdigest()
