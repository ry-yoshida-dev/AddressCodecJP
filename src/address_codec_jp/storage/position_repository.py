import sqlite3
from collections.abc import Iterable, Sequence
from itertools import batched
from typing import ClassVar

from geo_coordinate import GeodeticCrs

from address_codec_jp.domain.address_code import AddressCode
from address_codec_jp.domain.address_point import AddressPoint
from address_codec_jp.domain.coordinate_bounds import CoordinateBounds
from address_codec_jp.domain.lot_number import LotNumber
from address_codec_jp.domain.lot_system import LotSystem
from address_codec_jp.domain.representative_point import RepresentativePoint
from address_codec_jp.domain.town_position import TownPosition
from address_codec_jp.storage.area_position import AreaPosition
from address_codec_jp.storage.lot_entry import LotEntry
from address_codec_jp.storage.lot_position import LotPosition
from address_codec_jp.storage.lot_removal import LotRemoval
from address_codec_jp.storage.position_changes import PositionChanges
from address_codec_jp.storage.position_record import PositionRecord


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
        Open SQLite connection owned by ``AddressDatabase``.
    """

    _SCHEMA: ClassVar[tuple[str, ...]] = (
        """
        CREATE TABLE area_positions (
            lg_code TEXT PRIMARY KEY,
            longitude REAL NOT NULL,
            latitude REAL NOT NULL,
            epsg INTEGER NOT NULL
        )
        """,
        """
        CREATE TABLE town_positions (
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
        CREATE TABLE lot_entries (
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
        CREATE INDEX lot_entries_by_number
        ON lot_entries (lg_code, machiaza_id, lot_system, block, residence)
        """,
        """
        CREATE INDEX town_positions_by_coordinate
        ON town_positions (latitude, longitude)
        """,
        """
        CREATE TABLE lot_positions (
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
        """
        CREATE INDEX lot_positions_by_coordinate
        ON lot_positions (latitude, longitude)
        """,
    )
    _TOWN_KEYED_TABLES: ClassVar[tuple[str, ...]] = (
        "town_positions",
        "lot_entries",
        "lot_positions",
    )
    _ABSENT_RESIDENCE: ClassVar[int] = 0
    _BATCH_SIZE: ClassVar[int] = 10000

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection: sqlite3.Connection = connection
        self._is_position_imported: bool = False
        self._is_lot_imported: bool = False

    def create_schema(self) -> None:
        """Create the position tables."""
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
            ``True`` when a point of a prefecture, municipality, or town is stored.
        """
        if not self._is_position_imported:
            row = self._fetch_first(
                "SELECT EXISTS (SELECT 1 FROM area_positions) "
                + "OR EXISTS (SELECT 1 FROM town_positions)",
                (),
            )
            self._is_position_imported = row is not None and bool(row[0])
        return self._is_position_imported

    @property
    def is_lot_imported(self) -> bool:
        """
        Tell whether any block, residence, or parcel number has been imported.

        A positive answer is cached, because imports only add numbers.

        Returns
        -------
        bool
            ``True`` when a block, residence, or parcel master has been imported.
        """
        if not self._is_lot_imported:
            row = self._fetch_first("SELECT EXISTS (SELECT 1 FROM lot_entries)", ())
            self._is_lot_imported = row is not None and bool(row[0])
        return self._is_lot_imported

    def has_lots(self, lg_code: str, machiaza_id: str) -> bool:
        """
        Tell whether any lot number of a town has been imported.

        Parameters
        ----------
        lg_code : str
            Six-digit local government code.
        machiaza_id : str
            Seven-digit town identifier.

        Returns
        -------
        bool
            ``True`` when a block, residence, or parcel of the town is stored.
        """
        row = self._fetch_first(
            "SELECT EXISTS (SELECT 1 FROM lot_entries WHERE lg_code = ? AND machiaza_id = ?)",
            (lg_code, machiaza_id),
        )
        return row is not None and bool(row[0])

    def contains_lot(self, lg_code: str, machiaza_id: str, lot: LotNumber) -> bool:
        """
        Tell whether lot numbers are registered in a town under either numbering system.

        Parameters
        ----------
        lg_code : str
            Six-digit local government code.
        machiaza_id : str
            Seven-digit town identifier.
        lot : LotNumber
            Block and residence numbers. Without a residence, any residence of the block
            counts.

        Returns
        -------
        bool
            ``True`` when a block, residence, or parcel with the numbers is stored.

        Raises
        ------
        ValueError
            If ``lot`` has no block number.
        """
        block, residence = self._to_number_columns(lot)
        residence_condition = "" if lot.residence is None else " AND residence = ?"
        parameters: list[str | int] = [lg_code, machiaza_id, block]
        if lot.residence is not None:
            parameters.append(residence)
        row = self._fetch_first(
            "SELECT EXISTS (SELECT 1 FROM lot_entries WHERE lg_code = ? AND machiaza_id = ? "
            + f"AND block = ?{residence_condition})",
            parameters,
        )
        return row is not None and bool(row[0])

    def save_all(self, records: Iterable[PositionRecord]) -> PositionChanges:
        """
        Store records in one transaction, replacing records with the same identifiers.

        Removals delete the lot numbers of abolished lots, so that a newer number master
        drops them; their points stay unused, because lots are located through numbers.

        Parameters
        ----------
        records : Iterable[PositionRecord]
            Records read from the registry.

        Returns
        -------
        PositionChanges
            Numbers of stored records and of removed lot numbers.
        """
        stored_count = 0
        removed_count = 0
        with self._connection:
            for chunk in batched(records, self._BATCH_SIZE):
                removals = [record for record in chunk if isinstance(record, LotRemoval)]
                self._save_chunk(chunk)
                stored_count += len(chunk) - len(removals)
                removed_count += self._connection.executemany(
                    "DELETE FROM lot_entries WHERE lg_code = ? AND machiaza_id = ? "
                    + "AND lot_system = ? AND lot_id = ?",
                    [
                        (
                            removal.lg_code,
                            removal.machiaza_id,
                            removal.lot_system.value,
                            removal.lot_id,
                        )
                        for removal in removals
                    ],
                ).rowcount
        return PositionChanges(stored_count=stored_count, removed_count=removed_count)

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
                case LotRemoval():
                    pass
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

    def remove_orphans(self) -> int:
        """
        Remove points and lot numbers of areas that are not in the town table.

        Prefecture points are kept, because prefectures have no row of their own.

        Returns
        -------
        int
            Number of removed rows.
        """
        removed_count = 0
        with self._connection:
            removed_count += self._connection.execute(
                "DELETE FROM area_positions WHERE substr(lg_code, 3, 3) != '000' "
                + "AND lg_code NOT IN (SELECT lg_code FROM towns)"
            ).rowcount
            for table in self._TOWN_KEYED_TABLES:
                removed_count += self._connection.execute(
                    f"DELETE FROM {table} WHERE NOT EXISTS (SELECT 1 FROM towns AS t "
                    + f"WHERE t.lg_code = {table}.lg_code AND t.machiaza_id = {table}.machiaza_id)"
                ).rowcount
        return removed_count

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

    def list_lot_points(self, bounds: CoordinateBounds) -> list[AddressPoint]:
        """
        List the points of blocks, residences, and parcels within bounds.

        Only lots whose number master and position extension are both imported are listed.

        Parameters
        ----------
        bounds : CoordinateBounds
            Search area on the published datums.

        Returns
        -------
        list[AddressPoint]
            Codes with lot numbers and their points.
        """
        rows: list[tuple[object, ...]] = self._connection.execute(
            "SELECT p.lg_code, p.machiaza_id, e.block, e.residence, "
            + "p.longitude, p.latitude, p.epsg FROM lot_positions AS p "
            + "JOIN lot_entries AS e USING (lg_code, machiaza_id, lot_system, lot_id) "
            + "WHERE p.latitude BETWEEN ? AND ? AND p.longitude BETWEEN ? AND ?",
            self._to_bound_parameters(bounds),
        ).fetchall()
        return [
            AddressPoint(
                code=AddressCode(
                    lg_code=str(row[0]),
                    machiaza_id=str(row[1]),
                    lot=self._to_lot(row[2], row[3]),
                ),
                point=self._to_point(row[4:]),
            )
            for row in rows
        ]

    def list_town_points(self, bounds: CoordinateBounds) -> list[AddressPoint]:
        """
        List the points of towns within bounds.

        Parameters
        ----------
        bounds : CoordinateBounds
            Search area on the published datums.

        Returns
        -------
        list[AddressPoint]
            Town codes and their points.
        """
        rows: list[tuple[object, ...]] = self._connection.execute(
            "SELECT lg_code, machiaza_id, longitude, latitude, epsg FROM town_positions "
            + "WHERE latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ?",
            self._to_bound_parameters(bounds),
        ).fetchall()
        return [
            AddressPoint(
                code=AddressCode(lg_code=str(row[0]), machiaza_id=str(row[1])),
                point=self._to_point(row[2:]),
            )
            for row in rows
        ]

    def _to_bound_parameters(self, bounds: CoordinateBounds) -> tuple[float, float, float, float]:
        return (
            bounds.south_degrees,
            bounds.north_degrees,
            bounds.west_degrees,
            bounds.east_degrees,
        )

    def _to_lot(self, block: object, residence: object) -> LotNumber:
        if not (isinstance(block, int) and isinstance(residence, int)):
            raise RuntimeError(f"Malformed lot numbers: {block!r}, {residence!r}.")
        return LotNumber(
            block=block, residence=None if residence == self._ABSENT_RESIDENCE else residence
        )

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
