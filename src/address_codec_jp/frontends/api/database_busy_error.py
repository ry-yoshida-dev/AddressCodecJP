import sqlite3
from typing import ClassVar, Self


class DatabaseBusyError(RuntimeError):
    """
    Error of a query that met the database locked by another process, answered with 503.

    The lock is released when the other process, such as ``cache prepare``, finishes
    writing, so the request can be retried shortly.
    """

    RETRY_AFTER_SECONDS: ClassVar[int] = 1

    _BUSY_CODES: ClassVar[frozenset[int]] = frozenset({sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED})
    _PRIMARY_CODE_MASK: ClassVar[int] = 0xFF

    @classmethod
    def is_busy(cls, error: sqlite3.OperationalError) -> bool:
        """
        Tell whether an SQLite error reports a database locked by another connection.

        Parameters
        ----------
        error : sqlite3.OperationalError
            Error raised by a query.

        Returns
        -------
        bool
            ``True`` for ``SQLITE_BUSY`` and ``SQLITE_LOCKED``, including their
            extended codes; ``False`` for an error that carries no SQLite code.
        """
        error_code: object = getattr(error, "sqlite_errorcode", None)
        if not isinstance(error_code, int):
            return False
        return error_code & cls._PRIMARY_CODE_MASK in cls._BUSY_CODES

    @classmethod
    def from_error(cls, error: sqlite3.OperationalError) -> Self:
        """
        Describe a locked database without the detail of the SQLite error.

        Parameters
        ----------
        error : sqlite3.OperationalError
            Error for which ``is_busy`` holds.

        Returns
        -------
        Self
            Error asking to retry after ``RETRY_AFTER_SECONDS``.
        """
        return cls(
            "The address database is being updated by another process; retry in "
            + f"{cls.RETRY_AFTER_SECONDS} second ({error})."
        )
