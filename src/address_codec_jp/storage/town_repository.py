import sqlite3
from collections.abc import Iterable
from itertools import batched
from pathlib import Path
from types import TracebackType
from typing import ClassVar, Self

from address_codec_jp.domain.municipality import Municipality
from address_codec_jp.domain.prefecture import Prefecture
from address_codec_jp.domain.town import Town
from address_codec_jp.storage.import_summary import ImportSummary


class TownRepository:
    """
    SQLite-backed store of town records.

    Parameters
    ----------
    connection : sqlite3.Connection
        Open SQLite connection to a database that holds the town table.
    """

    _COLUMNS: ClassVar[str] = (
        "lg_code, machiaza_id, prefecture_name, county_name, city_name, ward_name, "
        + "oaza_name, chome_name, chome_number, koaza_name, is_registered"
    )
    _SCHEMA: ClassVar[str] = """
        CREATE TABLE IF NOT EXISTS towns (
            lg_code TEXT NOT NULL,
            machiaza_id TEXT NOT NULL,
            prefecture_name TEXT NOT NULL,
            county_name TEXT NOT NULL,
            city_name TEXT NOT NULL,
            ward_name TEXT NOT NULL,
            oaza_name TEXT NOT NULL,
            chome_name TEXT NOT NULL,
            chome_number INTEGER,
            koaza_name TEXT NOT NULL,
            is_registered INTEGER NOT NULL,
            PRIMARY KEY (lg_code, machiaza_id)
        )
    """
    _BATCH_SIZE: ClassVar[int] = 10000

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection: sqlite3.Connection = connection

    @classmethod
    def open(cls, database_path: Path | str) -> Self:
        """
        Open an existing repository database in read-only mode.

        Parameters
        ----------
        database_path : Path | str
            SQLite file created by ``create``.

        Returns
        -------
        Self
            Repository bound to the database.

        Raises
        ------
        FileNotFoundError
            If the file does not exist.
        ValueError
            If the file is an SQLite database without the town table.
        """
        path = Path(database_path)
        if not path.is_file():
            raise FileNotFoundError(f"Town database not found: {database_path}.")
        connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
        table_row: tuple[object, ...] | None = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'towns'"
        ).fetchone()
        if table_row is None:
            connection.close()
            raise ValueError(f"{database_path} is not a town database. Import a town master.")
        return cls(connection)

    @classmethod
    def create(cls, database_path: Path | str) -> Self:
        """
        Open a repository database, creating the file if needed.

        Parameters
        ----------
        database_path : Path | str
            SQLite file path, or ``":memory:"`` for an in-memory database.

        Returns
        -------
        Self
            Repository bound to the database.
        """
        connection = sqlite3.connect(database_path)
        _ = connection.execute(cls._SCHEMA)
        return cls(connection)

    @property
    def connection(self) -> sqlite3.Connection:
        """
        Connection to the database, shared with the position repository.

        Returns
        -------
        sqlite3.Connection
            Open connection owned by this repository.
        """
        return self._connection

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
        """Close the underlying connection."""
        self._connection.close()

    def replace_all(self, towns: Iterable[Town]) -> ImportSummary:
        """
        Replace every stored town with the given towns in one transaction.

        Rows repeated with identical contents are stored once. Oaza-level towns are then
        added for oaza registered only by chome. An ABR town ID consists of a four-digit
        oaza part and a three-digit chome part, so such a town gets the chome part ``000``
        and ``is_registered`` set to ``False``.

        Parameters
        ----------
        towns : Iterable[Town]
            Towns read from the registry.

        Returns
        -------
        ImportSummary
            Numbers of stored and added towns.

        Raises
        ------
        ValueError
            If one town ID appears with different contents. Nothing is changed then.
        """
        with self._connection:
            _ = self._connection.execute("DROP TABLE IF EXISTS temp.incoming_towns")
            _ = self._connection.execute(
                f"CREATE TEMP TABLE incoming_towns AS SELECT {self._COLUMNS} FROM towns LIMIT 0"
            )
            for chunk in batched(towns, self._BATCH_SIZE):
                _ = self._connection.executemany(
                    f"INSERT INTO incoming_towns ({self._COLUMNS}) "
                    + "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        (
                            town.lg_code,
                            town.machiaza_id,
                            town.prefecture_name,
                            town.county_name,
                            town.city_name,
                            town.ward_name,
                            town.oaza_name,
                            town.chome_name,
                            town.chome_number,
                            town.koaza_name,
                            town.is_registered,
                        )
                        for town in chunk
                    ],
                )
            conflicts: list[tuple[object, ...]] = self._connection.execute(
                f"SELECT lg_code, machiaza_id FROM (SELECT DISTINCT {self._COLUMNS} "
                + "FROM incoming_towns) GROUP BY lg_code, machiaza_id HAVING count(*) > 1 "
                + "LIMIT 5"
            ).fetchall()
            if conflicts:
                _ = self._connection.execute("DROP TABLE temp.incoming_towns")
                raise ValueError(
                    "Town IDs appear with different contents: "
                    + ", ".join(f"{row[0]}-{row[1]}" for row in conflicts)
                    + "."
                )
            _ = self._connection.execute("DELETE FROM towns")
            registered_cursor = self._connection.execute(
                f"INSERT INTO towns ({self._COLUMNS}) "
                + f"SELECT DISTINCT {self._COLUMNS} FROM incoming_towns"
            )
            _ = self._connection.execute("DROP TABLE temp.incoming_towns")
            complemented_cursor = self._connection.execute(
                f"INSERT OR IGNORE INTO towns ({self._COLUMNS}) "
                + "SELECT lg_code, substr(machiaza_id, 1, 4) || '000', prefecture_name, "
                + "county_name, city_name, ward_name, oaza_name, '', NULL, '', 0 "
                + "FROM towns WHERE chome_number IS NOT NULL "
                + "GROUP BY lg_code, substr(machiaza_id, 1, 4)"
            )
        return ImportSummary(
            registered_count=registered_cursor.rowcount,
            complemented_count=complemented_cursor.rowcount,
        )

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
        KeyError
            If no town has the identifiers.
        """
        rows: list[tuple[object, ...]] = self._connection.execute(
            f"SELECT {self._COLUMNS} FROM towns WHERE lg_code = ? AND machiaza_id = ?",
            (lg_code, machiaza_id),
        ).fetchall()
        if not rows:
            raise KeyError(f"Town {lg_code}-{machiaza_id} is not registered.")
        return self._to_town(rows[0])

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
        KeyError
            If no town of the municipality is registered.
        """
        municipalities = self._query_municipalities("WHERE lg_code = ?", (lg_code,))
        if not municipalities:
            raise KeyError(f"Municipality {lg_code} is not registered.")
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
        KeyError
            If no town of the prefecture is registered.
        """
        next_prefecture_code = f"{int(prefecture_code) + 1:02d}"
        municipalities = self._query_municipalities(
            "WHERE lg_code >= ? AND lg_code < ?", (prefecture_code, next_prefecture_code)
        )
        if not municipalities:
            raise KeyError(f"Prefecture {prefecture_code} is not registered.")
        return municipalities[0].prefecture

    def list_municipalities(self) -> list[Municipality]:
        """
        List all municipalities that have at least one town.

        Returns
        -------
        list[Municipality]
            Municipalities ordered by local government code.
        """
        return self._query_municipalities("", ())

    def _query_municipalities(
        self, where_clause: str, parameters: tuple[str, ...]
    ) -> list[Municipality]:
        rows: list[tuple[object, ...]] = self._connection.execute(
            "SELECT DISTINCT lg_code, prefecture_name, county_name, city_name, ward_name "
            + f"FROM towns {where_clause} ORDER BY lg_code",
            parameters,
        ).fetchall()
        return [
            Municipality(
                lg_code=str(row[0]),
                prefecture_name=str(row[1]),
                county_name=str(row[2]),
                city_name=str(row[3]),
                ward_name=str(row[4]),
            )
            for row in rows
        ]

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
            Towns ordered by town identifier.
        """
        rows: list[tuple[object, ...]] = self._connection.execute(
            f"SELECT {self._COLUMNS} FROM towns WHERE lg_code = ? ORDER BY machiaza_id",
            (lg_code,),
        ).fetchall()
        return [self._to_town(row) for row in rows]

    def _to_town(self, row: tuple[object, ...]) -> Town:
        chome_number = row[8]
        return Town(
            lg_code=str(row[0]),
            machiaza_id=str(row[1]),
            prefecture_name=str(row[2]),
            county_name=str(row[3]),
            city_name=str(row[4]),
            ward_name=str(row[5]),
            oaza_name=str(row[6]),
            chome_name=str(row[7]),
            chome_number=chome_number if isinstance(chome_number, int) else None,
            koaza_name=str(row[9]),
            is_registered=bool(row[10]),
        )
