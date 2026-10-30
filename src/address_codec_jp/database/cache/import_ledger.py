from pathlib import Path

from address_codec_jp.database.cache.area_target import AreaTarget
from address_codec_jp.database.cache.file_signature import DatabaseFileSignature
from address_codec_jp.database.storage import AddressDatabase


class ImportLedger:
    """
    Memory of the registry files and area datasets that need no download.

    Files and datasets in the import log of the database are read once, and read again
    after ``forget`` or when the file has changed since, such as when another process
    added some. Those the sites do not publish leave no trace in the log, so they are
    remembered apart and survive ``forget`` until ``reset``, instead of being requested
    again after every addition. A database file replaced or rebuilt, such as by
    ``DatabaseCache.refresh`` or ``clear`` in another process, resets the ledger.
    """

    def __init__(self) -> None:
        self._imported_names: set[str] = set()
        self._imported_areas: set[AreaTarget] = set()
        self._missing_names: set[str] = set()
        self._missing_areas: set[AreaTarget] = set()
        self._is_read: bool = False
        self._signature: DatabaseFileSignature | None = None

    def read(self, database_path: Path) -> None:
        """
        Load the import log of a database unless it has been loaded from the same state.

        Parameters
        ----------
        database_path : Path
            Database of the cache.

        Raises
        ------
        FileNotFoundError
            If the database does not exist.
        """
        signature = DatabaseFileSignature.of(database_path)
        if self._is_read and signature == self._signature:
            return
        if (
            self._signature is not None
            and signature is not None
            and not self._signature.is_same_file(signature)
        ):
            self.reset()
        else:
            self.forget()
        with AddressDatabase.open_read_only(database_path) as database:
            self._imported_names.update(item.source_name for item in database.imports.list_all())
            self._imported_areas.update(
                AreaTarget(item.source, item.lg_code) for item in database.areas.list_imports()
            )
        self._signature = signature
        self._is_read = True

    def is_registry_file_settled(self, file_name: str) -> bool:
        """
        Tell whether a registry file is imported or known to be unpublished.

        Parameters
        ----------
        file_name : str
            Distributed name of the file.

        Returns
        -------
        bool
            ``True`` when the file needs no download.
        """
        return file_name in self._imported_names or file_name in self._missing_names

    def is_area_settled(self, target: AreaTarget) -> bool:
        """
        Tell whether an area dataset is imported or known to be unpublished.

        Parameters
        ----------
        target : AreaTarget
            Dataset of a municipality.

        Returns
        -------
        bool
            ``True`` when the dataset needs no download.
        """
        return target in self._imported_areas or target in self._missing_areas

    def settle_registry_file(self, file_name: str, *, is_published: bool) -> None:
        """
        Record a registry file as imported or as unpublished.

        Parameters
        ----------
        file_name : str
            Distributed name of the file.
        is_published : bool
            Whether the file was downloaded and imported.
        """
        if is_published:
            self._imported_names.add(file_name)
        else:
            self._missing_names.add(file_name)

    def settle_area(self, target: AreaTarget, *, is_published: bool) -> None:
        """
        Record an area dataset as imported or as unpublished.

        Parameters
        ----------
        target : AreaTarget
            Dataset of a municipality.
        is_published : bool
            Whether any file of the dataset was downloaded and imported.
        """
        if is_published:
            self._imported_areas.add(target)
        else:
            self._missing_areas.add(target)

    def forget(self) -> None:
        """Forget the import log so that it is read again, keeping unpublished items."""
        self._imported_names = set()
        self._imported_areas = set()
        self._is_read = False

    def reset(self) -> None:
        """Forget everything, such as after the database has been replaced."""
        self.forget()
        self._missing_names = set()
        self._missing_areas = set()
        self._signature = None
