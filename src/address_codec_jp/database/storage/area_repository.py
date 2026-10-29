import sqlite3
from collections.abc import Iterable
from datetime import datetime
from typing import ClassVar

from address_codec_jp.address import AddressCode
from address_codec_jp.database.storage.area_import import AreaImport
from address_codec_jp.database.storage.area_record import AreaRecord
from address_codec_jp.geometry import AreaShape
from address_codec_jp.results import AreaSource


class AreaRepository:
    """
    SQLite-backed store of area shapes and the log of the area files imported.

    Shapes are serialized by ``AreaShape.to_bytes`` and indexed by their bounding boxes
    in an R*Tree, so that the shapes around a position are found without reading the
    others.

    Parameters
    ----------
    connection : sqlite3.Connection
        Open SQLite connection owned by ``AddressDatabase``.
    """

    _SCHEMA: ClassVar[tuple[str, ...]] = (
        """
        CREATE TABLE area_shapes (
            id INTEGER PRIMARY KEY,
            code TEXT NOT NULL,
            source TEXT NOT NULL,
            shape BLOB NOT NULL,
            UNIQUE (code, source)
        )
        """,
        """
        CREATE VIRTUAL TABLE area_shape_bounds USING rtree(
            id, west_degrees, east_degrees, south_degrees, north_degrees
        )
        """,
        """
        CREATE TABLE area_imports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            lg_code TEXT NOT NULL,
            source_name TEXT NOT NULL,
            source_sha256 TEXT NOT NULL,
            imported_at TEXT NOT NULL,
            stored_count INTEGER NOT NULL,
            unmatched_count INTEGER NOT NULL
        )
        """,
    )

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection: sqlite3.Connection = connection

    def create_schema(self) -> None:
        """Create the area tables."""
        for statement in self._SCHEMA:
            _ = self._connection.execute(statement)

    @property
    def is_area_imported(self) -> bool:
        """
        Tell whether any shape is stored.

        Returns
        -------
        bool
            ``True`` when shapes can be looked up.
        """
        rows: list[tuple[object, ...]] = self._connection.execute(
            "SELECT EXISTS (SELECT 1 FROM area_shapes)"
        ).fetchall()
        return rows[0][0] == 1

    def save_all(self, records: Iterable[AreaRecord]) -> int:
        """
        Store shapes within the caller's transaction, replacing those of the same code.

        Parameters
        ----------
        records : Iterable[AreaRecord]
            Shapes to store.

        Returns
        -------
        int
            Number of stored shapes.
        """
        stored_count = 0
        for record in records:
            box = record.shape.bounds
            rows: list[tuple[object, ...]] = self._connection.execute(
                "INSERT INTO area_shapes (code, source, shape) VALUES (?, ?, ?) "
                + "ON CONFLICT (code, source) DO UPDATE SET shape = excluded.shape "
                + "RETURNING id",
                (str(record.code), record.source.value, record.shape.to_bytes()),
            ).fetchall()
            _ = self._connection.execute(
                "INSERT OR REPLACE INTO area_shape_bounds VALUES (?, ?, ?, ?, ?)",
                (
                    rows[0][0],
                    box.west_degrees,
                    box.east_degrees,
                    box.south_degrees,
                    box.north_degrees,
                ),
            )
            stored_count += 1
        return stored_count

    def find(self, code: AddressCode, source: AreaSource) -> AreaShape | None:
        """
        Fetch the shape of a code.

        Parameters
        ----------
        code : AddressCode
            Code of the shape.
        source : AreaSource
            Dataset of the shape.

        Returns
        -------
        AreaShape | None
            Stored shape, or ``None`` when none is stored.
        """
        rows: list[tuple[object, ...]] = self._connection.execute(
            "SELECT shape FROM area_shapes WHERE code = ? AND source = ?",
            (str(code), source.value),
        ).fetchall()
        return None if not rows else self._to_shape(rows[0][0])

    def list_by_prefix(self, code_prefix: str, source: AreaSource) -> list[AreaRecord]:
        """
        List the shapes whose codes start with a prefix.

        Parameters
        ----------
        code_prefix : str
            Start of the codes, such as ``131016-`` for a municipality or
            ``131016-0011`` for an oaza.
        source : AreaSource
            Dataset of the shapes.

        Returns
        -------
        list[AreaRecord]
            Shapes ordered by code.
        """
        rows: list[tuple[object, ...]] = self._connection.execute(
            "SELECT code, source, shape FROM area_shapes "
            + "WHERE code >= ? AND code < ? AND source = ? ORDER BY code",
            (code_prefix, code_prefix + "\uffff", source.value),
        ).fetchall()
        return [self._to_record(row) for row in rows]

    def list_containing(
        self, longitude_degrees: float, latitude_degrees: float
    ) -> list[AreaRecord]:
        """
        List the shapes that contain a position.

        Parameters
        ----------
        longitude_degrees : float
            Longitude on JGD2011.
        latitude_degrees : float
            Latitude on JGD2011.

        Returns
        -------
        list[AreaRecord]
            Containing shapes ordered by code.
        """
        rows: list[tuple[object, ...]] = self._connection.execute(
            "SELECT area_shapes.code, area_shapes.source, area_shapes.shape "
            + "FROM area_shape_bounds JOIN area_shapes USING (id) "
            + "WHERE west_degrees <= ? AND east_degrees >= ? "
            + "AND south_degrees <= ? AND north_degrees >= ? ORDER BY area_shapes.code",
            (longitude_degrees, longitude_degrees, latitude_degrees, latitude_degrees),
        ).fetchall()
        records = [self._to_record(row) for row in rows]
        return [
            record
            for record in records
            if record.shape.contains(longitude_degrees, latitude_degrees)
        ]

    def add_import(self, area_import: AreaImport) -> None:
        """
        Append an import to the log within the caller's transaction.

        Parameters
        ----------
        area_import : AreaImport
            Completed import.
        """
        _ = self._connection.execute(
            "INSERT INTO area_imports (source, lg_code, source_name, source_sha256, "
            + "imported_at, stored_count, unmatched_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                area_import.source.value,
                area_import.lg_code,
                area_import.source_name,
                area_import.source_sha256,
                area_import.imported_at.isoformat(),
                area_import.stored_count,
                area_import.unmatched_count,
            ),
        )

    def list_imports(self) -> list[AreaImport]:
        """
        List all logged area imports.

        Returns
        -------
        list[AreaImport]
            Imports from the oldest to the newest.
        """
        rows: list[tuple[object, ...]] = self._connection.execute(
            "SELECT source, lg_code, source_name, source_sha256, imported_at, "
            + "stored_count, unmatched_count FROM area_imports ORDER BY id"
        ).fetchall()
        return [self._to_import(row) for row in rows]

    def _to_record(self, row: tuple[object, ...]) -> AreaRecord:
        code, source, shape = row
        if not (isinstance(code, str) and isinstance(source, str)):
            raise RuntimeError(f"Malformed area row: {code!r}, {source!r}.")
        return AreaRecord(
            code=AddressCode.parse(code), source=AreaSource(source), shape=self._to_shape(shape)
        )

    def _to_shape(self, value: object) -> AreaShape:
        if not isinstance(value, bytes):
            raise RuntimeError(f"Malformed area shape of type {type(value).__name__}.")
        return AreaShape.from_bytes(value)

    def _to_import(self, row: tuple[object, ...]) -> AreaImport:
        source, lg_code, source_name, source_sha256, imported_at, stored, unmatched = row
        if not (
            isinstance(source, str)
            and isinstance(lg_code, str)
            and isinstance(source_name, str)
            and isinstance(source_sha256, str)
            and isinstance(imported_at, str)
            and isinstance(stored, int)
            and isinstance(unmatched, int)
        ):
            raise RuntimeError(f"Malformed area import row: {row!r}.")
        return AreaImport(
            source=AreaSource(source),
            lg_code=lg_code,
            source_name=source_name,
            source_sha256=source_sha256,
            imported_at=datetime.fromisoformat(imported_at),
            stored_count=stored,
            unmatched_count=unmatched,
        )
