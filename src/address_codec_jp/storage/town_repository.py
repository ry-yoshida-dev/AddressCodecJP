import sqlite3
from collections.abc import Iterable
from itertools import batched
from typing import ClassVar

from address_codec_jp.domain.municipality import Municipality
from address_codec_jp.domain.prefecture import Prefecture
from address_codec_jp.domain.town import Town
from address_codec_jp.errors.address_not_found_error import AddressNotFoundError
from address_codec_jp.errors.registry_format_error import RegistryFormatError
from address_codec_jp.storage.town_replacement import TownReplacement


class TownRepository:
    """
    SQLite-backed store of municipalities and town records.

    Municipality names are stored once per municipality, and postal codes in a table of
    their own, because a town may have several.

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
        + "WHERE p.lg_code = t.lg_code AND p.machiaza_id = t.machiaza_id) FROM towns AS t"
    )
    _TABLES: ClassVar[tuple[str, ...]] = ("municipalities", "towns", "town_postal_codes")
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
            PRIMARY KEY (lg_code, machiaza_id)
        )
        """,
        """
        CREATE TABLE town_postal_codes (
            lg_code TEXT NOT NULL,
            machiaza_id TEXT NOT NULL,
            postal_code TEXT NOT NULL,
            PRIMARY KEY (lg_code, machiaza_id, postal_code)
        )
        """,
        """
        CREATE INDEX town_postal_codes_by_code
        ON town_postal_codes (postal_code)
        """,
    )
    _POSTAL_CODE_SEPARATOR: ClassVar[str] = ";"
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
        Replace every stored municipality and town with the given towns in one transaction.

        Rows repeated with identical contents are stored once. Oaza-level towns are then
        added for oaza registered only by chome. An ABR town ID consists of a four-digit
        oaza part and a three-digit chome part, so such a town gets the chome part ``000``
        and ``is_registered`` set to ``False``. It takes the postal codes of all its
        chome.

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
            with different municipality names. Nothing is changed then.
        """
        with self._connection:
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
            self._drop_incoming()
            complemented_cursor = self._connection.execute(
                f"INSERT OR IGNORE INTO towns ({self._TOWN_COLUMNS}) "
                + "SELECT lg_code, substr(machiaza_id, 1, 4) || '000', oaza_name, '', NULL, '', "
                + "oaza_kana, '', '', 0 FROM towns WHERE chome_number IS NOT NULL "
                + "GROUP BY lg_code, substr(machiaza_id, 1, 4)"
            )
            _ = self._connection.execute(
                "INSERT OR IGNORE INTO town_postal_codes "
                + "SELECT p.lg_code, oaza.machiaza_id, p.postal_code "
                + "FROM town_postal_codes AS p "
                + "JOIN towns AS chome USING (lg_code, machiaza_id) "
                + "JOIN towns AS oaza ON oaza.lg_code = p.lg_code "
                + "AND oaza.machiaza_id = substr(p.machiaza_id, 1, 4) || '000' "
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
                        self._POSTAL_CODE_SEPARATOR.join(town.postal_codes),
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
        rows: list[tuple[object, ...]] = self._connection.execute(
            f"{self._TOWN_SELECT} WHERE t.lg_code = ? AND t.machiaza_id = ?",
            (lg_code, machiaza_id),
        ).fetchall()
        if not rows:
            raise AddressNotFoundError(f"Town {lg_code}-{machiaza_id} is not registered.")
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
        next_prefecture_code = f"{int(prefecture_code) + 1:02d}"
        municipalities = self._query_municipalities(
            "WHERE lg_code >= ? AND lg_code < ?", (prefecture_code, next_prefecture_code)
        )
        if not municipalities:
            raise AddressNotFoundError(f"Prefecture {prefecture_code} is not registered.")
        return municipalities[0].prefecture

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

    def _to_town(self, row: tuple[object, ...], municipality: Municipality) -> Town:
        chome_number = row[4]
        postal_codes = row[10]
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
            is_registered=bool(row[9]),
            postal_codes=tuple(sorted(postal_codes.split(self._POSTAL_CODE_SEPARATOR)))
            if isinstance(postal_codes, str)
            else (),
        )
