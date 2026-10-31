import asyncio
import logging
import sqlite3
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import ClassVar

from address_codec_jp.address_codec import AddressCodec
from address_codec_jp.database.cache import DatabaseCache, DatabaseFileSignature
from address_codec_jp.errors import DatasetNotImportedError
from address_codec_jp.frontends.api.database_busy_error import DatabaseBusyError
from address_codec_jp.frontends.api.dataset_coverage import DatasetCoverage
from address_codec_jp.frontends.api.opened_codec import OpenedCodec

_LOGGER: logging.Logger = logging.getLogger(__name__)


class CodecPool:
    """
    Worker threads of a web service, each with its own codec on a prepared cache.

    A codec must be used in the thread that opened it, so queries run on a fixed set of
    threads that open a codec on first use. Nothing is downloaded on use. When the
    database file has been replaced, such as by ``DatabaseCache.refresh`` in another
    process, each thread reopens its codec before its next query; when it has been
    modified in place, such as by ``DatabaseCache.prepare``, the coverage is read again.
    When it has been deleted, such as by ``DatabaseCache.clear``, queries fail with
    ``DatasetNotImportedError`` until it is prepared again.

    Parameters
    ----------
    cache_directory : Path | None
        Directory of the prepared cache, or ``None`` for the default directory.
    thread_count : int
        Number of worker threads.

    Raises
    ------
    ValueError
        If ``thread_count`` is not positive.
    """

    CLOSE_TIMEOUT_SECONDS: ClassVar[float] = 30.0

    def __init__(self, cache_directory: Path | None, thread_count: int) -> None:
        if thread_count <= 0:
            raise ValueError(f"thread_count must be positive, got {thread_count}.")
        self._cache: DatabaseCache = DatabaseCache.default(
            directory=cache_directory, is_download_allowed=False
        )
        self._thread_count: int = thread_count
        self._executor: ThreadPoolExecutor = ThreadPoolExecutor(
            max_workers=thread_count, thread_name_prefix="address-codec"
        )
        self._codecs: dict[int, OpenedCodec] = {}
        self._lock: threading.Lock = threading.Lock()
        self._coverage: DatasetCoverage = DatasetCoverage(frozenset(), frozenset(), frozenset(), {})
        self._coverage_signature: DatabaseFileSignature | None = None

    @property
    def database_path(self) -> Path:
        """
        Database file the codecs read.

        Returns
        -------
        Path
            Path of the cache database.
        """
        return self._cache.path

    def check(self) -> None:
        """
        Verify that the cache has been built, so that a misconfigured service fails at start.

        Raises
        ------
        DatasetNotImportedError
            If the cache has not been built.
        UnsupportedDatabaseError
            If the file is not a database of this version of the library.
        """
        AddressCodec.open(cache=self._cache).close()

    async def run[ResultType](
        self, query: Callable[[AddressCodec, DatasetCoverage], ResultType]
    ) -> ResultType:
        """
        Run a query on a worker thread.

        Parameters
        ----------
        query : Callable[[AddressCodec, DatasetCoverage], ResultType]
            Function of the thread's codec and the current coverage of the cache.

        Returns
        -------
        ResultType
            Result of ``query``.

        Raises
        ------
        DatasetNotImportedError
            If the database file has been deleted since the start.
        DatabaseBusyError
            If another process holds a lock on the database.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, self._run, query)

    def close(self) -> None:
        """
        Close the codecs in the threads that opened them and stop the threads.

        Every thread is asked to close its codec. A thread still busy with a query after
        ``CLOSE_TIMEOUT_SECONDS``, or a codec that fails to close, is logged and does not
        keep the threads from stopping; a codec left open is closed when it is
        collected.
        """
        barrier = threading.Barrier(self._thread_count, timeout=self.CLOSE_TIMEOUT_SECONDS)
        futures = [
            self._executor.submit(self._close_thread_codec, barrier)
            for _ in range(self._thread_count)
        ]
        for future in futures:
            error = future.exception()
            if error is not None:
                _LOGGER.warning("A worker thread did not close its codec cleanly.", exc_info=error)
        self._executor.shutdown()
        with self._lock:
            unclosed_count = len(self._codecs)
            self._codecs.clear()
        if unclosed_count:
            _LOGGER.warning("%d codecs were left open by busy worker threads.", unclosed_count)

    def _run[ResultType](
        self, query: Callable[[AddressCodec, DatasetCoverage], ResultType]
    ) -> ResultType:
        signature = self._read_signature()
        try:
            codec = self._thread_codec(signature)
            return query(codec, self._current_coverage(codec, signature))
        except sqlite3.OperationalError as error:
            if DatabaseBusyError.is_busy(error):
                raise DatabaseBusyError.from_error(error) from error
            raise

    def _read_signature(self) -> DatabaseFileSignature:
        signature = DatabaseFileSignature.of(self._cache.path)
        if signature is None:
            raise DatasetNotImportedError(
                "The address database is not prepared on this server; run "
                + "address-codec-jp cache prepare."
            )
        return signature

    def _thread_codec(self, signature: DatabaseFileSignature) -> AddressCodec:
        thread_id = threading.get_ident()
        with self._lock:
            opened = self._codecs.get(thread_id)
        if opened is not None and opened.signature.is_same_file(signature):
            return opened.codec
        if opened is not None:
            opened.codec.close()
        codec = AddressCodec.open(cache=self._cache)
        with self._lock:
            self._codecs[thread_id] = OpenedCodec(codec, signature)
        return codec

    def _current_coverage(
        self, codec: AddressCodec, signature: DatabaseFileSignature
    ) -> DatasetCoverage:
        with self._lock:
            if self._coverage_signature == signature:
                return self._coverage
            coverage = DatasetCoverage.from_status(
                self._cache.describe(), codec.list_area_imports()
            )
            self._coverage = coverage
            self._coverage_signature = signature
            return coverage

    def _close_thread_codec(self, barrier: threading.Barrier) -> None:
        try:
            with self._lock:
                opened = self._codecs.pop(threading.get_ident(), None)
            if opened is not None:
                opened.codec.close()
        finally:
            _ = barrier.wait()
