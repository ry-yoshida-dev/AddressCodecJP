import os
import shutil
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import ClassVar, Self

import platformdirs

from address_codec_jp.domain.address_code import AddressCode
from address_codec_jp.domain.prefecture import Prefecture
from address_codec_jp.download.distributed_file import DistributedFile
from address_codec_jp.download.registry_downloader import RegistryDownloader
from address_codec_jp.registry.abr_dataset import AbrDataset
from address_codec_jp.registry.distribution_scope import DistributionScope
from address_codec_jp.registry_importer import RegistryImporter
from address_codec_jp.storage.address_database import AddressDatabase


class DatabaseCache:
    """
    Address database built on first use from the registry download site.

    The database is first built with the nationwide town master and the representative
    points of all prefectures, municipalities, and towns, which takes about 15 MB of
    downloads and 180 MB on disk. Blocks, residences, and land parcels are added by
    ``ensure_lots`` when an area needs them, from the residence indication and land
    parcel files of its municipality. Each schema version has its own file, so a new
    version of the library builds a new database instead of failing on an old one. The
    database is built in a temporary directory and moved into place when complete, so an
    interrupted build never leaves a partial database.

    Parameters
    ----------
    directory : Path
        Directory that holds the database.
    downloader : RegistryDownloader
        Downloader of the registry files.

    Examples
    --------
    >>> database_path = DatabaseCache.default().ensure()  # doctest: +SKIP
    """

    DIRECTORY_VARIABLE: ClassVar[str] = "ADDRESS_CODEC_JP_CACHE_DIR"
    BASE_URL_VARIABLE: ClassVar[str] = "ADDRESS_CODEC_JP_BASE_URL"
    _APPLICATION_NAME: ClassVar[str] = "address-codec-jp"

    def __init__(self, directory: Path, downloader: RegistryDownloader) -> None:
        self._directory: Path = directory
        self._downloader: RegistryDownloader = downloader
        self._settled_names: set[str] = set()
        self._is_import_log_read: bool = False

    @classmethod
    def default(cls) -> Self:
        """
        Create the cache configured by environment variables.

        ``ADDRESS_CODEC_JP_CACHE_DIR`` names the directory, the user cache directory of
        the platform by default, and ``ADDRESS_CODEC_JP_BASE_URL`` the download site or a
        mirror, ``RegistryDownloader.DEFAULT_BASE_URL`` by default.

        Returns
        -------
        Self
            Cache in the configured directory.
        """
        configured_directory = os.environ.get(cls.DIRECTORY_VARIABLE, "")
        directory = (
            Path(configured_directory)
            if configured_directory
            else platformdirs.user_cache_path(cls._APPLICATION_NAME)
        )
        base_url = os.environ.get(cls.BASE_URL_VARIABLE, "") or RegistryDownloader.DEFAULT_BASE_URL
        return cls(directory, RegistryDownloader(base_url))

    @property
    def path(self) -> Path:
        """
        Path of the database.

        Returns
        -------
        Path
            File such as ``towns-v3.sqlite3`` in the cache directory.
        """
        return self._directory / f"towns-v{AddressDatabase.SCHEMA_VERSION}.sqlite3"

    @property
    def is_built(self) -> bool:
        """
        Tell whether the database has been built.

        Returns
        -------
        bool
            ``True`` when ``path`` exists.
        """
        return self.path.is_file()

    def ensure(self) -> Path:
        """
        Build the database unless it has been built.

        Returns
        -------
        Path
            Path of the database.

        Raises
        ------
        RegistryDownloadError
            If a registry file cannot be downloaded.
        """
        if not self.is_built:
            self._build()
        return self.path

    def ensure_lots(self, lg_codes: Iterable[str]) -> None:
        """
        Add the blocks, residences, and land parcels of some areas unless already added.

        Parameters
        ----------
        lg_codes : Iterable[str]
            Six-digit local government codes. The residence indication and land parcel
            files of each municipality are added; prefecture codes and files the download
            site does not distribute are skipped.

        Raises
        ------
        ValueError
            If a code is malformed.
        RegistryDownloadError
            If a registry file cannot be downloaded.
        """
        database_path = self.ensure()
        self._read_import_log(database_path)
        targets = [
            target
            for target in self._plan_lots(lg_codes)
            if target.file_name not in self._settled_names
        ]
        if not targets:
            return
        working_directory = Path(tempfile.mkdtemp(dir=self._directory))
        try:
            downloaded = [
                self._downloader.download_if_distributed(target, working_directory)
                for target in targets
            ]
            paths = [path for path in downloaded if path is not None]
            if paths:
                with RegistryImporter.open(database_path) as importer:
                    _ = importer.import_files(paths)
            self._settled_names.update(target.file_name for target in targets)
        finally:
            shutil.rmtree(working_directory, ignore_errors=True)

    def _build(self) -> None:
        self._directory.mkdir(parents=True, exist_ok=True)
        working_directory = Path(tempfile.mkdtemp(dir=self._directory))
        try:
            paths = [
                self._downloader.download(target, working_directory) for target in self._plan()
            ]
            database_path = working_directory / self.path.name
            with RegistryImporter.open(database_path) as importer:
                _ = importer.import_files(paths)
            _ = database_path.replace(self.path)
        finally:
            shutil.rmtree(working_directory, ignore_errors=True)

    def _read_import_log(self, database_path: Path) -> None:
        if self._is_import_log_read:
            return
        with AddressDatabase.open_read_only(database_path) as database:
            self._settled_names.update(
                dataset_import.source_name for dataset_import in database.imports.list_all()
            )
        self._is_import_log_read = True

    def _plan(self) -> list[DistributedFile]:
        return [
            target
            for target in self._downloader.plan(Prefecture.list_codes())
            if self._is_town_level(target)
        ]

    def _plan_lots(self, lg_codes: Iterable[str]) -> list[DistributedFile]:
        municipality_codes = sorted(
            {lg_code for lg_code in lg_codes if not AddressCode.is_prefecture_code(lg_code)}
        )
        return self._downloader.plan_lots(municipality_codes)

    def _is_town_level(self, target: DistributedFile) -> bool:
        return (
            target.dataset.scope is DistributionScope.NATIONWIDE
            or target.dataset is AbrDataset.TOWN_POSITION
        )
