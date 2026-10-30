import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from types import TracebackType
from typing import ClassVar, Self

from address_codec_jp.database.storage.area.repository import AreaRepository
from address_codec_jp.database.storage.import_log_repository import ImportLogRepository
from address_codec_jp.database.storage.position_repository import PositionRepository
from address_codec_jp.database.storage.town_repository import TownRepository
from address_codec_jp.errors import UnsupportedDatabaseError


class AddressDatabase:
    """
    SQLite database that holds the imported registry datasets.

    The file is marked with an application ID and a schema version, so that a file of
    another application or of another version of this library is rejected instead of
    being misread or modified. A database holds one SQLite connection and must be used
    only in the thread that opened it. A connection waits up to ``BUSY_TIMEOUT_SECONDS``
    while another process writes, such as a cache adding the data of a municipality.

    Parameters
    ----------
    connection : sqlite3.Connection
        Open connection to a database with the current schema. It is closed by ``close``.
    is_writable : bool
        Whether the connection may modify the database.
    """

    APPLICATION_ID: ClassVar[int] = 0x41434A50
    SCHEMA_VERSION: ClassVar[int] = 5
    MEMORY_PATH: ClassVar[str] = ":memory:"
    BUSY_TIMEOUT_SECONDS: ClassVar[float] = 120.0

    def __init__(self, connection: sqlite3.Connection, *, is_writable: bool) -> None:
        self._connection: sqlite3.Connection = connection
        self._is_writable: bool = is_writable
        self._towns: TownRepository = TownRepository(connection)
        self._positions: PositionRepository = PositionRepository(connection)
        self._imports: ImportLogRepository = ImportLogRepository(connection)
        self._areas: AreaRepository = AreaRepository(connection)

    @classmethod
    def open_read_only(cls, database_path: Path | str) -> Self:
        """
        Open an existing database without permission to modify it.

        Parameters
        ----------
        database_path : Path | str
            SQLite file created by ``open_writable``.

        Returns
        -------
        Self
            Read-only database.

        Raises
        ------
        FileNotFoundError
            If the file does not exist.
        UnsupportedDatabaseError
            If the file is not a database of this version of the library.
        """
        path = Path(database_path)
        if not path.is_file():
            raise FileNotFoundError(f"Address database not found: {database_path}.")
        connection = sqlite3.connect(
            path.resolve().as_uri() + "?mode=ro", uri=True, timeout=cls.BUSY_TIMEOUT_SECONDS
        )
        database = cls(connection, is_writable=False)
        database._check_version(str(database_path))
        return database

    @classmethod
    def open_writable(cls, database_path: Path | str) -> Self:
        """
        Open a database for import, creating the file and its tables if needed.

        Parameters
        ----------
        database_path : Path | str
            SQLite file path, or ``":memory:"`` for an in-memory database.

        Returns
        -------
        Self
            Writable database.

        Raises
        ------
        UnsupportedDatabaseError
            If the file is not an SQLite database or holds other tables than a database
            of this version. Delete it and import again in that case.
        """
        target = database_path if database_path == cls.MEMORY_PATH else Path(database_path)
        database = cls(sqlite3.connect(target, timeout=cls.BUSY_TIMEOUT_SECONDS), is_writable=True)
        try:
            is_empty = database._is_empty()
        except sqlite3.DatabaseError as error:
            database.close()
            raise UnsupportedDatabaseError(f"{database_path} is not an SQLite database.") from error
        if is_empty:
            database._create_schema()
        else:
            database._check_version(str(database_path))
        return database

    @property
    def is_writable(self) -> bool:
        """
        Tell whether the database may be modified.

        Returns
        -------
        bool
            ``True`` when opened by ``open_writable``.
        """
        return self._is_writable

    @property
    def towns(self) -> TownRepository:
        """
        Store of municipalities and towns.

        Returns
        -------
        TownRepository
            Repository on this database.
        """
        return self._towns

    @property
    def positions(self) -> PositionRepository:
        """
        Store of representative points and lot numbers.

        Returns
        -------
        PositionRepository
            Repository on this database.
        """
        return self._positions

    @property
    def areas(self) -> AreaRepository:
        """
        Store of area shapes and the log of the area files imported.

        Returns
        -------
        AreaRepository
            Repository on this database.
        """
        return self._areas

    @property
    def imports(self) -> ImportLogRepository:
        """
        Log of the imported registry files.

        Returns
        -------
        ImportLogRepository
            Repository on this database.
        """
        return self._imports

    @contextmanager
    def transaction(self) -> Generator[None]:
        """
        Group writes of the repositories into one transaction.

        The writes are committed when the block ends and rolled back when it raises, so
        that an import is stored completely or not at all. Repositories never commit on
        their own.

        Yields
        ------
        None
            Control to the block that writes.

        Raises
        ------
        RuntimeError
            If the database was opened read-only.
        """
        if not self._is_writable:
            raise RuntimeError("The database was opened read-only.")
        with self._connection:
            yield

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
        """Close the connection."""
        self._connection.close()

    def _is_empty(self) -> bool:
        rows: list[tuple[object, ...]] = self._connection.execute(
            "SELECT count(*) FROM sqlite_master"
        ).fetchall()
        return rows[0][0] == 0

    def _create_schema(self) -> None:
        with self._connection:
            self._towns.create_schema()
            self._positions.create_schema()
            self._imports.create_schema()
            self._areas.create_schema()
            _ = self._connection.execute(f"PRAGMA application_id = {self.APPLICATION_ID}")
            _ = self._connection.execute(f"PRAGMA user_version = {self.SCHEMA_VERSION}")

    def _check_version(self, description: str) -> None:
        try:
            application_id = self._read_pragma("application_id")
            schema_version = self._read_pragma("user_version")
        except sqlite3.DatabaseError as error:
            self.close()
            raise UnsupportedDatabaseError(f"{description} is not an SQLite database.") from error
        if application_id != self.APPLICATION_ID:
            self.close()
            raise UnsupportedDatabaseError(
                f"{description} is not an AddressCodecJP database. Import a town master "
                + "into a new file."
            )
        if schema_version != self.SCHEMA_VERSION:
            self.close()
            raise UnsupportedDatabaseError(
                f"{description} has schema version {schema_version}, but this version of "
                + f"AddressCodecJP uses {self.SCHEMA_VERSION}. Delete it and import again."
            )

    def _read_pragma(self, name: str) -> int:
        rows: list[tuple[object, ...]] = self._connection.execute(f"PRAGMA {name}").fetchall()
        value = rows[0][0]
        if not isinstance(value, int):
            raise RuntimeError(f"PRAGMA {name} returned {value!r}.")
        return value
