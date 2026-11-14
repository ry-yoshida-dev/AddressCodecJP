import sqlite3
from collections.abc import Iterable
from datetime import datetime
from typing import ClassVar

from address_codec_jp.address import AddressCode, DesignatedCity
from address_codec_jp.database.storage.area.census_record import CensusAreaRecord
from address_codec_jp.database.storage.area.imported_file import AreaImport
from address_codec_jp.database.storage.area.record import AreaRecord
from address_codec_jp.geometry import AreaShape
from address_codec_jp.results import AreaSource


class AreaRepository:
    """
    SQLite-backed store of area shapes and the log of the area files imported.

    Census small areas are stored under their own census codes, each with the towns it
    is matched to, so that a municipality is made of all its areas however their names
    were matched; land parcels are stored under their address codes. Shapes are
    serialized by ``AreaShape.to_bytes`` and indexed by their bounding boxes in R*Trees,
    so that the shapes around a position are found without reading the others.

    Parameters
    ----------
    connection : sqlite3.Connection
        Open SQLite connection owned by ``AddressDatabase``.
    """

    _SCHEMA: ClassVar[tuple[str, ...]] = (
        """
        CREATE TABLE census_areas (
            id INTEGER PRIMARY KEY,
            key_code TEXT NOT NULL UNIQUE,
            lg_code TEXT NOT NULL,
            name TEXT NOT NULL,
            is_land INTEGER NOT NULL,
            shape BLOB NOT NULL
        )
        """,
        "CREATE INDEX census_areas_by_municipality ON census_areas (lg_code)",
        """
        CREATE TABLE census_area_towns (
            census_area_id INTEGER NOT NULL,
            lg_code TEXT NOT NULL,
            machiaza_id TEXT NOT NULL,
            PRIMARY KEY (census_area_id, lg_code, machiaza_id)
        ) WITHOUT ROWID
        """,
        "CREATE INDEX census_area_towns_by_town ON census_area_towns (lg_code, machiaza_id)",
        """
        CREATE VIRTUAL TABLE census_area_bounds USING rtree(
            id, west_degrees, east_degrees, south_degrees, north_degrees
        )
        """,
        """
        CREATE TABLE parcel_shapes (
            id INTEGER PRIMARY KEY,
            code TEXT NOT NULL UNIQUE,
            shape BLOB NOT NULL
        )
        """,
        """
        CREATE VIRTUAL TABLE parcel_shape_bounds USING rtree(
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
    _OAZA_ID_LENGTH: ClassVar[int] = 4

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
            "SELECT EXISTS (SELECT 1 FROM census_areas) OR EXISTS (SELECT 1 FROM parcel_shapes)"
        ).fetchall()
        return rows[0][0] == 1

    def save_census_areas(self, records: Iterable[CensusAreaRecord]) -> int:
        """
        Store census areas within the caller's transaction, replacing those of the same code.

        Parameters
        ----------
        records : Iterable[CensusAreaRecord]
            Areas to store.

        Returns
        -------
        int
            Number of stored areas.
        """
        stored_count = 0
        for record in records:
            rows: list[tuple[object, ...]] = self._connection.execute(
                "INSERT INTO census_areas (key_code, lg_code, name, is_land, shape) "
                + "VALUES (?, ?, ?, ?, ?) ON CONFLICT (key_code) DO UPDATE SET "
                + "lg_code = excluded.lg_code, name = excluded.name, "
                + "is_land = excluded.is_land, shape = excluded.shape RETURNING id",
                (
                    record.key_code,
                    record.lg_code,
                    record.name,
                    int(record.is_land),
                    record.shape.to_bytes(),
                ),
            ).fetchall()
            area_id = rows[0][0]
            _ = self._connection.execute(
                "DELETE FROM census_area_towns WHERE census_area_id = ?", (area_id,)
            )
            _ = self._connection.executemany(
                "INSERT INTO census_area_towns VALUES (?, ?, ?)",
                [(area_id, town.lg_code, town.machiaza_id) for town in record.towns],
            )
            self._index_bounds("census_area_bounds", area_id, record.shape)
            stored_count += 1
        return stored_count

    def save_parcels(self, records: Iterable[AreaRecord]) -> int:
        """
        Store parcel shapes within the caller's transaction, replacing those of the same code.

        Parameters
        ----------
        records : Iterable[AreaRecord]
            Shapes from the registry maps, coded with their parcel numbers.

        Returns
        -------
        int
            Number of stored shapes.

        Raises
        ------
        ValueError
            If a record is not a parcel of the registry maps.
        """
        stored_count = 0
        for record in records:
            if record.source is not AreaSource.REGISTRY_MAP or not record.code.lot.is_land_parcel:
                raise ValueError(f"{record.code} from {record.source.value} is not a parcel.")
            rows: list[tuple[object, ...]] = self._connection.execute(
                "INSERT INTO parcel_shapes (code, shape) VALUES (?, ?) "
                + "ON CONFLICT (code) DO UPDATE SET shape = excluded.shape RETURNING id",
                (str(record.code), record.shape.to_bytes()),
            ).fetchall()
            self._index_bounds("parcel_shape_bounds", rows[0][0], record.shape)
            stored_count += 1
        return stored_count

    def find_parcel(self, code: AddressCode) -> AreaShape | None:
        """
        Fetch the shape of a parcel.

        Parameters
        ----------
        code : AddressCode
            Code with parcel numbers.

        Returns
        -------
        AreaShape | None
            Stored shape, or ``None`` when none is stored.
        """
        rows: list[tuple[object, ...]] = self._connection.execute(
            "SELECT shape FROM parcel_shapes WHERE code = ?", (str(code),)
        ).fetchall()
        return None if not rows else self._to_shape(rows[0][0])

    def find_town(self, code: AddressCode) -> AreaShape | None:
        """
        Combine the census areas matched to a town.

        Parameters
        ----------
        code : AddressCode
            Town code.

        Returns
        -------
        AreaShape | None
            Shapes of the areas, or ``None`` when none is matched to the town.

        Raises
        ------
        ValueError
            If ``code`` is not a town code.
        """
        if code.machiaza_id is None or code.lot.numbers:
            raise ValueError(f"{code} is not a town code.")
        return self._combine(
            "SELECT census_areas.shape FROM census_area_towns JOIN census_areas "
            + "ON census_areas.id = census_area_towns.census_area_id "
            + "WHERE census_area_towns.lg_code = ? AND census_area_towns.machiaza_id = ? "
            + "ORDER BY census_areas.key_code",
            (code.lg_code, code.machiaza_id),
        )

    def find_oaza(self, code: AddressCode) -> AreaShape | None:
        """
        Combine the census areas matched to any town of the oaza of a town.

        Parameters
        ----------
        code : AddressCode
            Town code whose first four digits of ``machiaza_id`` name the oaza.

        Returns
        -------
        AreaShape | None
            Shapes of the areas, or ``None`` when none is matched to the oaza.

        Raises
        ------
        ValueError
            If ``code`` is not a town code.
        """
        if code.machiaza_id is None or code.lot.numbers:
            raise ValueError(f"{code} is not a town code.")
        oaza_id = code.machiaza_id[: self._OAZA_ID_LENGTH]
        return self._combine(
            "SELECT shape FROM census_areas WHERE id IN (SELECT census_area_id "
            + "FROM census_area_towns WHERE lg_code = ? AND machiaza_id >= ? "
            + "AND machiaza_id < ?) ORDER BY key_code",
            (code.lg_code, oaza_id, oaza_id + "\uffff"),
        )

    def find_municipality(self, lg_code: str) -> AreaShape | None:
        """
        Combine every census area of a municipality, matched to a town or not.

        A designated city is made of the areas of all its wards.

        Parameters
        ----------
        lg_code : str
            Six-digit local government code.

        Returns
        -------
        AreaShape | None
            Shapes of the areas, or ``None`` when none is stored.
        """
        if DesignatedCity.is_code(lg_code):
            return self._combine(
                "SELECT shape FROM census_areas WHERE lg_code > ? AND lg_code < ? "
                + "ORDER BY lg_code, key_code",
                DesignatedCity.ward_code_bounds(lg_code),
            )
        return self._combine(
            "SELECT shape FROM census_areas WHERE lg_code = ? ORDER BY key_code", (lg_code,)
        )

    def list_containing(
        self, longitude_degrees: float, latitude_degrees: float
    ) -> list[AreaRecord]:
        """
        List the towns and parcels whose shapes contain a position.

        A town is listed with the shape of all its census areas, as ``find_town`` gives
        it, when one of them contains the position; areas matched to no town are left
        out.

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
        position = (longitude_degrees, longitude_degrees, latitude_degrees, latitude_degrees)
        bounds_filter = (
            "WHERE west_degrees <= ? AND east_degrees >= ? "
            + "AND south_degrees <= ? AND north_degrees >= ?"
        )
        census_rows: list[tuple[object, ...]] = self._connection.execute(
            "SELECT census_area_towns.lg_code, census_area_towns.machiaza_id, "
            + "census_areas.shape FROM census_area_bounds "
            + "JOIN census_areas ON census_areas.id = census_area_bounds.id "
            + "JOIN census_area_towns ON census_area_towns.census_area_id = census_areas.id "
            + bounds_filter,
            position,
        ).fetchall()
        towns = {
            AddressCode(lg_code=str(lg_code), machiaza_id=str(machiaza_id))
            for lg_code, machiaza_id, shape in census_rows
            if self._to_shape(shape).contains(longitude_degrees, latitude_degrees)
        }
        town_records = [
            AreaRecord(code=town, source=AreaSource.CENSUS_BOUNDARY, shape=shape)
            for town in towns
            if (shape := self.find_town(town)) is not None
        ]
        parcel_rows: list[tuple[object, ...]] = self._connection.execute(
            "SELECT parcel_shapes.code, parcel_shapes.shape FROM parcel_shape_bounds "
            + "JOIN parcel_shapes ON parcel_shapes.id = parcel_shape_bounds.id "
            + bounds_filter,
            position,
        ).fetchall()
        parcel_records = [
            AreaRecord(
                code=AddressCode.parse(str(code)),
                source=AreaSource.REGISTRY_MAP,
                shape=parcel_shape,
            )
            for code, shape in parcel_rows
            if (parcel_shape := self._to_shape(shape)).contains(longitude_degrees, latitude_degrees)
        ]
        return sorted(town_records + parcel_records, key=lambda record: str(record.code))

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

    def _index_bounds(self, table: str, row_id: object, shape: AreaShape) -> None:
        box = shape.bounds
        _ = self._connection.execute(
            f"INSERT OR REPLACE INTO {table} VALUES (?, ?, ?, ?, ?)",
            (row_id, box.west_degrees, box.east_degrees, box.south_degrees, box.north_degrees),
        )

    def _combine(self, query: str, parameters: tuple[str, ...]) -> AreaShape | None:
        rows: list[tuple[object, ...]] = self._connection.execute(query, parameters).fetchall()
        if not rows:
            return None
        return AreaShape(
            tuple(polygon for row in rows for polygon in self._to_shape(row[0]).polygons)
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
