import re
import shutil
import tempfile
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import ClassVar

from filelock import FileLock

from address_codec_jp.database.storage import AddressDatabase


class CacheDirectory:
    """
    Layout of the files in the directory of a cache.

    The database of the current schema version is ``towns-v{version}.sqlite3``. Builds
    run in ``build-*`` working directories, and writes are serialized across processes
    by the lock file ``cache.lock``. Databases of older schema versions and working
    directories untouched for ``STALE_WORKING_SECONDS`` are obsolete. Databases of newer
    versions are kept, so that an older and a newer library sharing the directory do not
    delete each other's database and rebuild their own again and again.

    Parameters
    ----------
    root : Path
        Directory of the cache; created when first written.
    """

    STALE_WORKING_SECONDS: ClassVar[float] = 86400.0
    _DATABASE_PATTERN: ClassVar[re.Pattern[str]] = re.compile(
        r"towns-v(?P<version>\d+)\.sqlite3(?:-journal|-wal|-shm)?"
    )
    _WORKING_PREFIX: ClassVar[str] = "build-"
    _LOCK_NAME: ClassVar[str] = "cache.lock"

    def __init__(self, root: Path) -> None:
        self._root: Path = root
        self._lock: FileLock = FileLock(root / self._LOCK_NAME)

    @property
    def root(self) -> Path:
        """
        Directory of the cache.

        Returns
        -------
        Path
            The directory given at construction.
        """
        return self._root

    @property
    def database_path(self) -> Path:
        """
        Path of the database of the current schema version.

        Returns
        -------
        Path
            File such as ``towns-v4.sqlite3`` in the directory.
        """
        return self._root / f"towns-v{AddressDatabase.SCHEMA_VERSION}.sqlite3"

    @contextmanager
    def locked(self) -> Generator[None]:
        """
        Hold the lock of the directory, which the same cache object may take again.

        Yields
        ------
        None
            Control while the lock is held.
        """
        self._root.mkdir(parents=True, exist_ok=True)
        with self._lock:
            yield

    def make_working_directory(self) -> Path:
        """
        Create an empty working directory for a build.

        Returns
        -------
        Path
            New ``build-*`` directory in the cache directory.
        """
        self._root.mkdir(parents=True, exist_ok=True)
        return Path(tempfile.mkdtemp(prefix=self._WORKING_PREFIX, dir=self._root))

    def list_obsolete(self) -> list[Path]:
        """
        List databases of older schema versions and stale working directories.

        Returns
        -------
        list[Path]
            Obsolete files and directories ordered by path.
        """
        if not self._root.is_dir():
            return []
        databases = [
            path
            for path in self._root.iterdir()
            if (version := self._schema_version(path)) is not None
            and version < AddressDatabase.SCHEMA_VERSION
        ]
        threshold = time.time() - self.STALE_WORKING_SECONDS
        working_directories = [
            path
            for path in self._root.glob(self._WORKING_PREFIX + "*")
            if path.is_dir() and path.stat().st_mtime < threshold
        ]
        return sorted([*databases, *working_directories])

    def remove_obsolete(self) -> list[Path]:
        """
        Delete the files listed by ``list_obsolete``.

        Returns
        -------
        list[Path]
            Deleted files and directories.
        """
        removed = self.list_obsolete()
        for path in removed:
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink(missing_ok=True)
        return removed

    def remove_database(self) -> list[Path]:
        """
        Delete the database of the current schema version and its journal.

        Returns
        -------
        list[Path]
            Deleted files.
        """
        if not self._root.is_dir():
            return []
        removed = sorted(self._root.glob(self.database_path.name + "*"))
        for path in removed:
            path.unlink()
        return removed

    def _schema_version(self, path: Path) -> int | None:
        match_result = self._DATABASE_PATTERN.fullmatch(path.name)
        return None if match_result is None else int(match_result.group("version"))
