import os
import shutil
import tempfile
from pathlib import Path
from typing import ClassVar, Self

import platformdirs

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

    The database holds the nationwide town master and the representative points of all
    prefectures, municipalities, and towns, which takes about 15 MB of downloads and
    180 MB on disk. Block and residence points are not included; import them into
    ``path`` to locate those levels. Each schema version has its own file, so a new
    version of the library builds a new database instead of failing on an old one. The
    database is built in a temporary directory and moved into place when complete, so
    an interrupted build never leaves a partial database.

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
    _APPLICATION_NAME: ClassVar[str] = "address-codec-jp"

    def __init__(self, directory: Path, downloader: RegistryDownloader) -> None:
        self._directory: Path = directory
        self._downloader: RegistryDownloader = downloader

    @classmethod
    def default(cls) -> Self:
        """
        Create the cache in the directory named by ``ADDRESS_CODEC_JP_CACHE_DIR``.

        Returns
        -------
        Self
            Cache in that directory, or in the user cache directory of the platform when
            the variable is unset or empty.
        """
        configured = os.environ.get(cls.DIRECTORY_VARIABLE, "")
        directory = (
            Path(configured) if configured else platformdirs.user_cache_path(cls._APPLICATION_NAME)
        )
        return cls(directory, RegistryDownloader())

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

    def _plan(self) -> list[DistributedFile]:
        return [
            target
            for target in self._downloader.plan(Prefecture.list_codes())
            if target.dataset.scope is DistributionScope.NATIONWIDE
            or target.dataset is AbrDataset.TOWN_POSITION
        ]
