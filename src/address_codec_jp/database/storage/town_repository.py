import sqlite3
from collections import defaultdict
from collections.abc import Collection, Iterable
from itertools import batched
from typing import ClassVar

from address_codec_jp.address import Municipality, Prefecture, Town
from address_codec_jp.database.storage.lot_system_column import LotSystemColumn
from address_codec_jp.database.storage.town_replacement import TownReplacement
from address_codec_jp.errors import AddressNotFoundError, RegistryFormatError


class TownRepository:
    """
    SQLite-backed store of municipalities and town records.

    Municipality names are stored once per municipality, and postal codes and numbering
    systems in tables of their own, because a town may have several.

    Parameters
    ----------
    connection : sqlite3.Connection
        Open SQLite connection owned by ``AddressDatabase``.
    """

    _MUNICIPALITY_COLUMN_NAMES: ClassVar[tuple[str, ...]] = (
        "lg_code",
        "prefecture_name",
        "county_name",
        "city_name",
        "ward_name",
        "prefecture_kana",
        "county_kana",
        "city_kana",
        "ward_kana",
    )
    _TOWN_COLUMN_NAMES: ClassVar[tuple[str, ...]] = (
        "lg_code",
        "machiaza_id",
        "oaza_name",
        "chome_name",
        "chome_number",
        "koaza_name",
        "oaza_kana",
        "chome_kana",
        "koaza_kana",
        "is_registered",
        "is_street_direction",
    )
    _MUNICIPALITY_COLUMNS: ClassVar[str] = ", ".join(_MUNICIPALITY_COLUMN_NAMES)
    _TOWN_COLUMNS: ClassVar[str] = ", ".join(_TOWN_COLUMN_NAMES)
    _INCOMING_COLUMNS: ClassVar[str] = (
        _MUNICIPALITY_COLUMNS + ", " + ", ".join(_TOWN_COLUMN_NAMES[1:]) + ", postal_codes"
    )
    _TOWN_SELECT: ClassVar[str] = (
        "SELECT "
        + ", ".join(f"t.{name}" for name in _TOWN_COLUMN_NAMES)
        + ", (SELECT group_concat(p.postal_code, ';') FROM town_postal_codes AS p "
        + "WHERE p.lg_code = t.lg_code AND p.machiaza_id = t.machiaza_id)"
        + ", (SELECT group_concat(l.lot_system, ';') FROM town_lot_systems AS l "
        + "WHERE l.lg_code = t.lg_code AND l.machiaza_id = t.machiaza_id) FROM towns AS t"
    )
    _TABLES: ClassVar[tuple[str, ...]] = (
        "municipalities",
        "towns",
        "town_postal_codes",
        "town_lot_systems",
    )
    _SCHEMA: ClassVar[tuple[str, ...]] = (
        """
        CREATE TABLE municipalities (
            lg_code TEXT PRIMARY KEY,
            prefecture_name TEXT NOT NULL,
            county_name TEXT NOT NULL,
            city_name TEXT NOT NULL,
            ward_name TEXT NOT NULL,
            prefecture_kana TEXT NOT NULL,
            county_kana TEXT NOT NULL,
            city_kana TEXT NOT NULL,
            ward_kana TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE towns (
            lg_code TEXT NOT NULL,
            machiaza_id TEXT NOT NULL,
            oaza_name TEXT NOT NULL,
            chome_name TEXT NOT NULL,
            chome_number INTEGER,
            koaza_name TEXT NOT NULL,
            oaza_kana TEXT NOT NULL,
            chome_kana TEXT NOT NULL,
            koaza_kana TEXT NOT NULL,
            is_registered INTEGER NOT NULL,
            is_street_direction INTEGER NOT NULL,
            PRIMARY KEY (lg_code, machiaza_id)
        ) WITHOUT ROWID
        """,
        """
        CREATE INDEX towns_by_oaza_name
        ON towns (oaza_name)
        """,
        """
        CREATE INDEX towns_by_koaza_name
        ON towns (koaza_name)
        """,
        """
        CREATE TABLE town_postal_codes (
            lg_code TEXT NOT NULL,
            machiaza_id TEXT NOT NULL,
            postal_code TEXT NOT NULL,
            PRIMARY KEY (lg_code, machiaza_id, postal_code)
        ) WITHOUT ROWID
        """,
        """
        CREATE INDEX town_postal_codes_by_code
        ON town_postal_codes (postal_code)
        """,
        """
        CREATE TABLE town_lot_systems (
            lg_code TEXT NOT NULL,
            machiaza_id TEXT NOT NULL,
            lot_system INTEGER NOT NULL,
            PRIMARY KEY (lg_code, machiaza_id, lot_system)
        ) WITHOUT ROWID
        """,
    )
    _VALUE_SEPARATOR: ClassVar[str] = ";"
    _CONFLICT_REPORT_LIMIT: ClassVar[int] = 5
    _BATCH_SIZE: ClassVar[int] = 10000

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection: sqlite3.Connection = connection

    def create_schema(self) -> None:
        """Create the town tables."""
        for statement in self._SCHEMA:
            _ = self._connection.execute(statement)

    def replace_all(self, towns: Iterable[Town]) -> TownReplacement:
        """
        Replace every stored municipality and town with the given towns.

        Runs within the caller's transaction, so that a failure keeps the previous towns.

        Rows repeated with identical contents are stored once. The registry lists a town
        once per numbering system where residence indication covers only part of it, so
        rows that differ only in their numbering systems are merged. Oaza-level towns are
        then added for oaza registered only by chome. An ABR town ID consists of a
        four-digit oaza part and a three-digit chome part, so such a town gets the chome
        part ``000`` and ``is_registered`` set to ``False``. It takes the postal codes and
        numbering systems of all its chome.

        Parameters
        ----------
        towns : Iterable[Town]
            Towns read from the registry.

        Returns
        -------
        TownReplacement
            Numbers of stored and added towns.

        Raises
        ------
        RegistryFormatError
            If one town ID appears with different contents, or one local government code
            with different municipality names.
        """
        self._load_incoming(towns)
        self._reject_conflicts()
        for table in self._TABLES:
            _ = self._connection.execute(f"DELETE FROM {table}")
        _ = self._connection.execute(
            f"INSERT INTO municipalities ({self._MUNICIPALITY_COLUMNS}) "
            + f"SELECT DISTINCT {self._MUNICIPALITY_COLUMNS} FROM incoming_towns"
        )
        registered_cursor = self._connection.execute(
            f"INSERT INTO towns ({self._TOWN_COLUMNS}) "
            + f"SELECT DISTINCT {self._TOWN_COLUMNS} FROM incoming_towns"
        )
        _ = self._connection.execute(
            "INSERT OR IGNORE INTO town_postal_codes SELECT * FROM incoming_postal_codes"
        )
        _ = self._connection.execute(
            "INSERT OR IGNORE INTO town_lot_systems SELECT * FROM incoming_lot_systems"
        )
        self._drop_incoming()
        complemented_cursor = self._connection.execute(
            f"INSERT OR IGNORE INTO towns ({self._TOWN_COLUMNS}) "
            + "SELECT lg_code, substr(machiaza_id, 1, 4) || '000', oaza_name, '', NULL, '', "
            + "oaza_kana, '', '', 0, 0 FROM towns WHERE chome_number IS NOT NULL "
            + "GROUP BY lg_code, substr(machiaza_id, 1, 4)"
        )
        for table, column in (
            ("town_postal_codes", "postal_code"),
            ("town_lot_systems", "lot_system"),
        ):
            _ = self._connection.execute(
                f"INSERT OR IGNORE INTO {table} "
                + f"SELECT c.lg_code, oaza.machiaza_id, c.{column} FROM {table} AS c "
                + "JOIN towns AS chome USING (lg_code, machiaza_id) "
                + "JOIN towns AS oaza ON oaza.lg_code = c.lg_code "
                + "AND oaza.machiaza_id = substr(c.machiaza_id, 1, 4) || '000' "
                + "WHERE chome.chome_number IS NOT NULL AND oaza.is_registered = 0"
            )
        return TownReplacement(
            registered_count=registered_cursor.rowcount,
            complemented_count=complemented_cursor.rowcount,
        )

    def _load_incoming(self, towns: Iterable[Town]) -> None:
        self._drop_incoming()
        _ = self._connection.execute(f"CREATE TEMP TABLE incoming_towns ({self._INCOMING_COLUMNS})")
        _ = self._connection.execute(
            "CREATE TEMP TABLE incoming_postal_codes AS SELECT * FROM town_postal_codes LIMIT 0"
        )
        _ = self._connection.execute(
            "CREATE TEMP TABLE incoming_lot_systems AS SELECT * FROM town_lot_systems LIMIT 0"
        )
        placeholders = ", ".join("?" for _ in self._INCOMING_COLUMNS.split(", "))
        for chunk in batched(towns, self._BATCH_SIZE):
            _ = self._connection.executemany(
                f"INSERT INTO incoming_towns VALUES ({placeholders})",
                [
                    (
                        town.lg_code,
                        town.municipality.prefecture_name,
                        town.municipality.county_name,
                        town.municipality.city_name,
                        town.municipality.ward_name,
                        town.municipality.prefecture_kana,
                        town.municipality.county_kana,
                        town.municipality.city_kana,
                        town.municipality.ward_kana,
                        town.machiaza_id,
                        town.oaza_name,
                        town.chome_name,
                        town.chome_number,
                        town.koaza_name,
                        town.oaza_kana,
                        town.chome_kana,
                        town.koaza_kana,
                        town.is_registered,
                        town.is_street_direction,
                        self._VALUE_SEPARATOR.join(town.postal_codes),
                    )
                    for town in chunk
                ],
            )
            _ = self._connection.executemany(
                "INSERT INTO incoming_postal_codes VALUES (?, ?, ?)",
                [
                    (town.lg_code, town.machiaza_id, postal_code)
                    for town in chunk
                    for postal_code in town.postal_codes
                ],
            )
            _ = self._connection.executemany(
                "INSERT INTO incoming_lot_systems VALUES (?, ?, ?)",
                [
                    (town.lg_code, town.machiaza_id, LotSystemColumn.encode(lot_system))
                    for town in chunk
                    for lot_system in town.lot_systems
                ],
            )

    def _reject_conflicts(self) -> None:
        town_conflicts: list[tuple[object, ...]] = self._connection.execute(
            f"SELECT lg_code, machiaza_id FROM (SELECT DISTINCT {self._INCOMING_COLUMNS} "
            + "FROM incoming_towns) GROUP BY lg_code, machiaza_id HAVING count(*) > 1 LIMIT ?",
            (self._CONFLICT_REPORT_LIMIT,),
        ).fetchall()
        municipality_conflicts: list[tuple[object, ...]] = self._connection.execute(
            f"SELECT lg_code FROM (SELECT DISTINCT {self._MUNICIPALITY_COLUMNS} "
            + "FROM incoming_towns) GROUP BY lg_code HAVING count(*) > 1 LIMIT ?",
            (self._CONFLICT_REPORT_LIMIT,),
        ).fetchall()
        if town_conflicts:
            self._drop_incoming()
            raise RegistryFormatError(
                "Town IDs appear with different contents: "
                + ", ".join(f"{row[0]}-{row[1]}" for row in town_conflicts)
                + "."
            )
        if municipality_conflicts:
            self._drop_incoming()
            raise RegistryFormatError(
                "Local government codes appear with different municipality names: "
                + ", ".join(str(row[0]) for row in municipality_conflicts)
                + "."
            )

    def _drop_incoming(self) -> None:
        _ = self._connection.execute("DROP TABLE IF EXISTS temp.incoming_towns")
        _ = self._connection.execute("DROP TABLE IF EXISTS temp.incoming_postal_codes")
        _ = self._connection.execute("DROP TABLE IF EXISTS temp.incoming_lot_systems")

    def get_town(self, lg_code: str, machiaza_id: str) -> Town:
        """
        Fetch one town by its identifiers.

        Parameters
        ----------
        lg_code : str
            Six-digit local government code.
        machiaza_id : str
            Seven-digit town identifier.

        Returns
        -------
        Town
            Matching town.

        Raises
        ------
        AddressNotFoundError
            If no town has the identifiers.
        """
        town = self.find_town(lg_code, machiaza_id)
        if town is None:
            raise AddressNotFoundError(f"Town {lg_code}-{machiaza_id} is not registered.")
        return town

    def find_town(self, lg_code: str, machiaza_id: str) -> Town | None:
        """
        Fetch one town by its identifiers when it is registered.

        Parameters
        ----------
        lg_code : str
            Six-digit local government code.
        machiaza_id : str
            Seven-digit town identifier.

        Returns
        -------
        Town | None
            Matching town, or ``None`` when no town has the identifiers.
        """
        rows: list[tuple[object, ...]] = self._connection.execute(
            f"{self._TOWN_SELECT} WHERE t.lg_code = ? AND t.machiaza_id = ?",
            (lg_code, machiaza_id),
        ).fetchall()
        if not rows:
            return None
        return self._to_town(rows[0], self.get_municipality(lg_code))

    def get_municipality(self, lg_code: str) -> Municipality:
        """
        Fetch one municipality by its local government code.

        Parameters
        ----------
        lg_code : str
            Six-digit local government code.

        Returns
        -------
        Municipality
            Matching municipality.

        Raises
        ------
        AddressNotFoundError
            If the municipality is not registered.
        """
        municipalities = self._query_municipalities("WHERE lg_code = ?", (lg_code,))
        if not municipalities:
            raise AddressNotFoundError(f"Municipality {lg_code} is not registered.")
        return municipalities[0]

    def get_prefecture(self, prefecture_code: str) -> Prefecture:
        """
        Fetch one prefecture by its two-digit code.

        Parameters
        ----------
        prefecture_code : str
            Two-digit prefecture code.

        Returns
        -------
        Prefecture
            Matching prefecture.

        Raises
        ------
        AddressNotFoundError
            If no municipality of the prefecture is registered.
        """
        municipalities = self.list_prefecture_municipalities(prefecture_code)
        if not municipalities:
            raise AddressNotFoundError(f"Prefecture {prefecture_code} is not registered.")
        return municipalities[0].prefecture

    def list_prefecture_municipalities(self, prefecture_code: str) -> list[Municipality]:
        """
        List the municipalities of a prefecture.

        Wards of a designated city are listed in place of the city.

        Parameters
        ----------
        prefecture_code : str
            Two-digit prefecture code.

        Returns
        -------
        list[Municipality]
            Municipalities ordered by local government code. Empty when none of the
            prefecture is registered.
        """
        next_prefecture_code = f"{int(prefecture_code) + 1:02d}"
        return self._query_municipalities(
            "WHERE lg_code >= ? AND lg_code < ?", (prefecture_code, next_prefecture_code)
        )

    def list_municipalities(self) -> list[Municipality]:
        """
        List all municipalities.

        Returns
        -------
        list[Municipality]
            Municipalities ordered by local government code.
        """
        return self._query_municipalities("", ())

    def _query_municipalities(
        self, condition: str, parameters: tuple[str, ...]
    ) -> list[Municipality]:
        rows: list[tuple[object, ...]] = self._connection.execute(
            f"SELECT {self._MUNICIPALITY_COLUMNS} FROM municipalities {condition} "
            + "ORDER BY lg_code",
            parameters,
        ).fetchall()
        return [
            Municipality(
                lg_code=str(row[0]),
                prefecture_name=str(row[1]),
                county_name=str(row[2]),
                city_name=str(row[3]),
                ward_name=str(row[4]),
                prefecture_kana=str(row[5]),
                county_kana=str(row[6]),
                city_kana=str(row[7]),
                ward_kana=str(row[8]),
            )
            for row in rows
        ]

    def list_municipality_codes(self, postal_code: str) -> set[str]:
        """
        List the municipalities that have a town with a postal code.

        Parameters
        ----------
        postal_code : str
            Seven-digit postal code.

        Returns
        -------
        set[str]
            Local government codes. Empty when no town is registered with the code.
        """
        rows: list[tuple[object, ...]] = self._connection.execute(
            "SELECT DISTINCT lg_code FROM town_postal_codes WHERE postal_code = ?",
            (postal_code,),
        ).fetchall()
        return {str(row[0]) for row in rows}

    def map_oaza_names(self) -> dict[str, set[str]]:
        """
        Map every oaza name to the municipalities that have a town under it.

        Returns
        -------
        dict[str, set[str]]
            Local government codes by oaza name. Towns without an oaza name are left out.
        """
        lg_codes_by_name: dict[str, set[str]] = defaultdict(set)
        rows: list[tuple[object, ...]] = self._connection.execute(
            "SELECT DISTINCT oaza_name, lg_code FROM towns WHERE oaza_name <> ''"
        ).fetchall()
        for row in rows:
            lg_codes_by_name[str(row[0])].add(str(row[1]))
        return dict(lg_codes_by_name)

    def list_street_municipality_codes(self) -> set[str]:
        """
        List the municipalities that have a town whose koaza is a street direction.

        Returns
        -------
        set[str]
            Local government codes; empty when no town is a street direction.
        """
        rows: list[tuple[object, ...]] = self._connection.execute(
            "SELECT DISTINCT lg_code FROM towns WHERE is_street_direction = 1"
        ).fetchall()
        return {str(row[0]) for row in rows}

    def list_town_names(self) -> set[str]:
        """
        List every oaza and koaza name.

        Returns
        -------
        set[str]
            Registry names as written. Empty names are left out.
        """
        rows: list[tuple[object, ...]] = self._connection.execute(
            "SELECT oaza_name FROM towns WHERE oaza_name <> '' "
            + "UNION SELECT koaza_name FROM towns WHERE koaza_name <> ''"
        ).fetchall()
        return {str(row[0]) for row in rows}

    def list_towns_named(self, names: Collection[str]) -> list[Town]:
        """
        List the towns whose oaza or koaza name is one of the names.

        Parameters
        ----------
        names : Collection[str]
            Oaza or koaza names as written in the registry.

        Returns
        -------
        list[Town]
            Towns ordered by local government code and town identifier.
        """
        if not names:
            return []
        placeholders = ", ".join("?" for _ in names)
        rows: list[tuple[object, ...]] = self._connection.execute(
            f"{self._TOWN_SELECT} WHERE t.oaza_name IN ({placeholders}) "
            + f"OR t.koaza_name IN ({placeholders}) ORDER BY t.lg_code, t.machiaza_id",
            (*names, *names),
        ).fetchall()
        return self._to_towns(rows)

    def list_towns_by_postal_code(self, postal_code: str) -> list[Town]:
        """
        List the registered towns that have a postal code.

        Oaza-level towns added on import are left out, because they only repeat the
        postal codes of their chome.

        Parameters
        ----------
        postal_code : str
            Seven-digit postal code.

        Returns
        -------
        list[Town]
            Towns ordered by local government code and town identifier. Empty when no
            town has the postal code.
        """
        rows: list[tuple[object, ...]] = self._connection.execute(
            f"{self._TOWN_SELECT} WHERE t.is_registered = 1 AND EXISTS (SELECT 1 "
            + "FROM town_postal_codes AS q WHERE q.lg_code = t.lg_code "
            + "AND q.machiaza_id = t.machiaza_id AND q.postal_code = ?) "
            + "ORDER BY t.lg_code, t.machiaza_id",
            (postal_code,),
        ).fetchall()
        return self._to_towns(rows)

    def list_towns(self, lg_code: str) -> list[Town]:
        """
        List towns of a municipality.

        Parameters
        ----------
        lg_code : str
            Six-digit local government code.

        Returns
        -------
        list[Town]
            Towns ordered by town identifier. Empty when the municipality is not
            registered.
        """
        municipalities = self._query_municipalities("WHERE lg_code = ?", (lg_code,))
        if not municipalities:
            return []
        rows: list[tuple[object, ...]] = self._connection.execute(
            f"{self._TOWN_SELECT} WHERE t.lg_code = ? ORDER BY t.machiaza_id", (lg_code,)
        ).fetchall()
        return [self._to_town(row, municipalities[0]) for row in rows]

    def list_top_towns(self, municipality: Municipality) -> list[Town]:
        """
        List the towns directly under a municipality.

        These are the oaza-level towns, whose chome part is ``000``, and the chome and
        koaza whose oaza is not registered, such as koaza without an oaza name.

        Parameters
        ----------
        municipality : Municipality
            Registered municipality.

        Returns
        -------
        list[Town]
            Towns ordered by town identifier.
        """
        rows: list[tuple[object, ...]] = self._connection.execute(
            f"{self._TOWN_SELECT} WHERE t.lg_code = ? AND (substr(t.machiaza_id, 5) = '000' "
            + "OR NOT EXISTS (SELECT 1 FROM towns AS o WHERE o.lg_code = t.lg_code "
            + "AND o.machiaza_id = substr(t.machiaza_id, 1, 4) || '000')) "
            + "ORDER BY t.machiaza_id",
            (municipality.lg_code,),
        ).fetchall()
        return [self._to_town(row, municipality) for row in rows]

    def list_oaza_members(self, oaza: Town) -> list[Town]:
        """
        List the chome and koaza of an oaza.

        Parameters
        ----------
        oaza : Town
            Registered oaza-level town, whose chome part is ``000``.

        Returns
        -------
        list[Town]
            Towns sharing the oaza part of the town identifier, ordered by town
            identifier.
        """
        rows: list[tuple[object, ...]] = self._connection.execute(
            f"{self._TOWN_SELECT} WHERE t.lg_code = ? AND t.machiaza_id > ? "
            + "AND t.machiaza_id <= ? ORDER BY t.machiaza_id",
            (oaza.lg_code, oaza.machiaza_id, oaza.machiaza_id[:4] + "999"),
        ).fetchall()
        return [self._to_town(row, oaza.municipality) for row in rows]

    def _to_towns(self, rows: list[tuple[object, ...]]) -> list[Town]:
        municipalities: dict[str, Municipality] = {}
        towns: list[Town] = []
        for row in rows:
            lg_code = str(row[0])
            if lg_code not in municipalities:
                municipalities[lg_code] = self.get_municipality(lg_code)
            towns.append(self._to_town(row, municipalities[lg_code]))
        return towns

    def _to_town(self, row: tuple[object, ...], municipality: Municipality) -> Town:
        chome_number = row[4]
        postal_codes = row[11]
        lot_systems = row[12]
        return Town(
            municipality=municipality,
            machiaza_id=str(row[1]),
            oaza_name=str(row[2]),
            chome_name=str(row[3]),
            chome_number=chome_number if isinstance(chome_number, int) else None,
            koaza_name=str(row[5]),
            oaza_kana=str(row[6]),
            chome_kana=str(row[7]),
            koaza_kana=str(row[8]),
            lot_systems=frozenset(
                LotSystemColumn.decode(value)
                for value in str(lot_systems).split(self._VALUE_SEPARATOR)
            ),
            is_registered=bool(row[9]),
            is_street_direction=bool(row[10]),
            postal_codes=tuple(sorted(postal_codes.split(self._VALUE_SEPARATOR)))
            if isinstance(postal_codes, str)
            else (),
        )
