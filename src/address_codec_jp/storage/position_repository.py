import sqlite3
from collections.abc import Iterable, Sequence
from itertools import batched
from typing import ClassVar

from geo_coordinate import GeodeticCrs

from address_codec_jp.domain.lot_number import LotNumber
from address_codec_jp.domain.lot_system import LotSystem
from address_codec_jp.domain.representative_point import RepresentativePoint
from address_codec_jp.storage.area_position import AreaPosition
from address_codec_jp.storage.lot_entry import LotEntry
from address_codec_jp.storage.lot_position import LotPosition
from address_codec_jp.storage.position_record import PositionRecord
from address_codec_jp.storage.town_position import TownPosition


class PositionRepository:
    """
    SQLite-backed store of representative points.

    Lot numbers and their points are stored in separate tables keyed by registry
    identifiers, so a number master and its position extension can be imported in
    either order and prefecture by prefecture. Points keep the datum they are published
    on.

    Parameters
    ----------
    connection : sqlite3.Connection
        Open SQLite connection. It is shared with the town repository and not closed here.
    """

    _SCHEMA: ClassVar[tuple[str, ...]] = (
        """
        CREATE TABLE IF NOT EXISTS area_positions (
            lg_code TEXT PRIMARY KEY,
            longitude REAL NOT NULL,
            latitude REAL NOT NULL,
            epsg INTEGER NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS town_positions (
            lg_code TEXT NOT NULL,
            machiaza_id TEXT NOT NULL,
            lot_system TEXT NOT NULL,
            longitude REAL NOT NULL,
            latitude REAL NOT NULL,
            epsg INTEGER NOT NULL,
            PRIMARY KEY (lg_code, machiaza_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS lot_entries (
            lg_code TEXT NOT NULL,
            machiaza_id TEXT NOT NULL,
            lot_system TEXT NOT NULL,
            lot_id TEXT NOT NULL,
            block INTEGER NOT NULL,
            residence INTEGER NOT NULL,
            PRIMARY KEY (lg_code, machiaza_id, lot_system, lot_id)
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS lot_entries_by_number
        ON lot_entries (lg_code, machiaza_id, lot_system, block, residence)
        """,
        """
        CREATE TABLE IF NOT EXISTS lot_positions (
            lg_code TEXT NOT NULL,
            machiaza_id TEXT NOT NULL,
            lot_system TEXT NOT NULL,
            lot_id TEXT NOT NULL,
            longitude REAL NOT NULL,
            latitude REAL NOT NULL,
            epsg INTEGER NOT NULL,
            PRIMARY KEY (lg_code, machiaza_id, lot_system, lot_id)
        )
        """,
    )
    _TABLES: ClassVar[tuple[str, ...]] = (
        "area_positions",
        "town_positions",
        "lot_entries",
        "lot_positions",
    )
    _ABSENT_RESIDENCE: ClassVar[int] = 0
    _BATCH_SIZE: ClassVar[int] = 10000

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection: sqlite3.Connection = connection
        self._is_position_imported: bool = False

    def create_schema(self) -> None:
        """Create the position tables if they do not exist."""
        with self._connection:
            for statement in self._SCHEMA:
                _ = self._connection.execute(statement)

    @property
    def is_position_imported(self) -> bool:
        """
        Tell whether any representative point has been imported.

        A positive answer is cached, because imports only add points.

        Returns
        -------
        bool
            ``True`` when the tables exist and hold a prefecture, municipality, or town.
        """
        if not self._is_position_imported:
            self._is_position_imported = self._query_position_imported()
        return self._is_position_imported

    def _query_position_imported(self) -> bool:
        table_count_row = self._fetch_first(
            "SELECT count(*) FROM sqlite_master WHERE type = 'table' AND name IN (?, ?, ?, ?)",
            self._TABLES,
        )
        if table_count_row is None or table_count_row[0] != len(self._TABLES):
            return False
        row = self._fetch_first(
            "SELECT EXISTS (SELECT 1 FROM area_positions) "
            + "OR EXISTS (SELECT 1 FROM town_positions)",
            (),
        )
        return row is not None and bool(row[0])

    def save_all(self, records: Iterable[PositionRecord]) -> int:
        """
        Store records in one transaction, replacing records with the same identifiers.

        Parameters
        ----------
        records : Iterable[PositionRecord]
            Records read from the registry.

        Returns
        -------
        int
            Number of stored records.
        """
        stored_count = 0
        with self._connection:
            for chunk in batched(records, self._BATCH_SIZE):
                self._save_chunk(chunk)
                stored_count += len(chunk)
        return stored_count

    def _save_chunk(self, records: Sequence[PositionRecord]) -> None:
        area_rows: list[tuple[str, float, float, int]] = []
        town_rows: list[tuple[str, str, str, float, float, int]] = []
        entry_rows: list[tuple[str, str, str, str, int, int]] = []
        lot_position_rows: list[tuple[str, str, str, str, float, float, int]] = []
        for record in records:
            match record:
                case AreaPosition(lg_code=lg_code, point=point):
                    area_rows.append((lg_code, point.longitude, point.latitude, point.crs.epsg))
                case TownPosition():
                    town_rows.append(
                        (
                            record.lg_code,
                            record.machiaza_id,
                            record.lot_system.value,
                            record.point.longitude,
                            record.point.latitude,
                            record.point.crs.epsg,
                        )
                    )
                case LotEntry():
                    entry_rows.append(
                        (
                            record.lg_code,
                            record.machiaza_id,
                            record.lot_system.value,
                            record.lot_id,
                            *self._to_number_columns(record.lot),
                        )
                    )
                case LotPosition():
                    lot_position_rows.append(
                        (
                            record.lg_code,
                            record.machiaza_id,
                            record.lot_system.value,
                            record.lot_id,
                            record.point.longitude,
                            record.point.latitude,
                            record.point.crs.epsg,
                        )
                    )
        _ = self._connection.executemany(
            "INSERT OR REPLACE INTO area_positions VALUES (?, ?, ?, ?)", area_rows
        )
        _ = self._connection.executemany(
            "INSERT OR REPLACE INTO town_positions VALUES (?, ?, ?, ?, ?, ?)", town_rows
        )
        _ = self._connection.executemany(
            "INSERT OR REPLACE INTO lot_entries VALUES (?, ?, ?, ?, ?, ?)", entry_rows
        )
        _ = self._connection.executemany(
            "INSERT OR REPLACE INTO lot_positions VALUES (?, ?, ?, ?, ?, ?, ?)",
            lot_position_rows,
        )

    def find_area(self, lg_code: str) -> RepresentativePoint | None:
        """
        Fetch the point of a prefecture or municipality.

        Parameters
        ----------
        lg_code : str
            Six-digit local government code.

        Returns
        -------
        RepresentativePoint | None
            Point of the area, or ``None`` when none is imported.
        """
        row = self._fetch_first(
            "SELECT longitude, latitude, epsg FROM area_positions WHERE lg_code = ?",
            (lg_code,),
        )
        return None if row is None else self._to_point(row)

    def find_town(self, lg_code: str, machiaza_id: str) -> TownPosition | None:
        """
        Fetch the point and lot numbering of a town.

        Parameters
        ----------
        lg_code : str
            Six-digit local government code.
        machiaza_id : str
            Seven-digit town identifier.

        Returns
        -------
        TownPosition | None
            Position of the town, or ``None`` when none is imported.
        """
        row = self._fetch_first(
            "SELECT lot_system, longitude, latitude, epsg FROM town_positions "
            + "WHERE lg_code = ? AND machiaza_id = ?",
            (lg_code, machiaza_id),
        )
        if row is None:
            return None
        return TownPosition(
            lg_code=lg_code,
            machiaza_id=machiaza_id,
            lot_system=LotSystem(str(row[0])),
            point=self._to_point(row[1:]),
        )

    def find_lot(
        self, lg_code: str, machiaza_id: str, lot_systems: Sequence[LotSystem], lot: LotNumber
    ) -> RepresentativePoint | None:
        """
        Fetch the point of a block, residence, or parcel by its numbers.

        Parameters
        ----------
        lg_code : str
            Six-digit local government code.
        machiaza_id : str
            Seven-digit town identifier.
        lot_systems : Sequence[LotSystem]
            Numbering systems to search, in order of preference.
        lot : LotNumber
            Block and residence numbers. ``block`` must be given.

        Returns
        -------
        RepresentativePoint | None
            Point of the first match, or ``None`` when no point is imported.

        Raises
        ------
        ValueError
            If ``lot`` has no block number.
        """
        block, residence = self._to_number_columns(lot)
        for lot_system in lot_systems:
            row = self._fetch_first(
                "SELECT p.longitude, p.latitude, p.epsg FROM lot_entries AS e "
                + "JOIN lot_positions AS p USING (lg_code, machiaza_id, lot_system, lot_id) "
                + "WHERE e.lg_code = ? AND e.machiaza_id = ? AND e.lot_system = ? "
                + "AND e.block = ? AND e.residence = ? ORDER BY e.lot_id LIMIT 1",
                (lg_code, machiaza_id, lot_system.value, block, residence),
            )
            if row is not None:
                return self._to_point(row)
        return None

    def _fetch_first(
        self, statement: str, parameters: Sequence[str | int]
    ) -> tuple[object, ...] | None:
        rows: list[tuple[object, ...]] = self._connection.execute(statement, parameters).fetchmany(
            1
        )
        return rows[0] if rows else None

    def _to_number_columns(self, lot: LotNumber) -> tuple[int, int]:
        if lot.block is None:
            raise ValueError("A lot position requires a block number.")
        return lot.block, self._ABSENT_RESIDENCE if lot.residence is None else lot.residence

    def _to_point(self, row: tuple[object, ...]) -> RepresentativePoint:
        longitude, latitude, epsg = row
        if not (
            isinstance(longitude, float) and isinstance(latitude, float) and isinstance(epsg, int)
        ):
            raise RuntimeError(f"Malformed position row: {row!r}.")
        return RepresentativePoint(longitude=longitude, latitude=latitude, crs=GeodeticCrs(epsg))
