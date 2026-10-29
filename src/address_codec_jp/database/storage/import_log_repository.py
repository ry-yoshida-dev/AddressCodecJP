import sqlite3
from datetime import datetime
from typing import ClassVar

from address_codec_jp.database.storage.dataset_import import DatasetImport
from address_codec_jp.datasets.address_base_registry import AbrDataset


class ImportLogRepository:
    """
    SQLite-backed log of the registry files imported into a database.

    Parameters
    ----------
    connection : sqlite3.Connection
        Open SQLite connection owned by ``AddressDatabase``.
    """

    _SCHEMA: ClassVar[str] = """
        CREATE TABLE dataset_imports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dataset TEXT NOT NULL,
            source_name TEXT NOT NULL,
            source_sha256 TEXT NOT NULL,
            imported_at TEXT NOT NULL,
            row_count INTEGER NOT NULL
        )
    """

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection: sqlite3.Connection = connection

    def create_schema(self) -> None:
        """Create the import log table."""
        _ = self._connection.execute(self._SCHEMA)

    def add(self, dataset_import: DatasetImport) -> None:
        """
        Append an import to the log within the caller's transaction.

        Parameters
        ----------
        dataset_import : DatasetImport
            Completed import.
        """
        _ = self._connection.execute(
            "INSERT INTO dataset_imports "
            + "(dataset, source_name, source_sha256, imported_at, row_count) "
            + "VALUES (?, ?, ?, ?, ?)",
            (
                dataset_import.dataset.name,
                dataset_import.source_name,
                dataset_import.source_sha256,
                dataset_import.imported_at.isoformat(),
                dataset_import.row_count,
            ),
        )

    def list_all(self) -> list[DatasetImport]:
        """
        List all logged imports.

        Returns
        -------
        list[DatasetImport]
            Imports from the oldest to the newest.
        """
        rows: list[tuple[object, ...]] = self._connection.execute(
            "SELECT dataset, source_name, source_sha256, imported_at, row_count "
            + "FROM dataset_imports ORDER BY id"
        ).fetchall()
        return [self._to_import(row) for row in rows]

    def _to_import(self, row: tuple[object, ...]) -> DatasetImport:
        dataset, source_name, source_sha256, imported_at, row_count = row
        if not (
            isinstance(dataset, str)
            and isinstance(source_name, str)
            and isinstance(source_sha256, str)
            and isinstance(imported_at, str)
            and isinstance(row_count, int)
        ):
            raise RuntimeError(f"Malformed import log row: {row!r}.")
        return DatasetImport(
            dataset=AbrDataset[dataset],
            source_name=source_name,
            source_sha256=source_sha256,
            imported_at=datetime.fromisoformat(imported_at),
            row_count=row_count,
        )
