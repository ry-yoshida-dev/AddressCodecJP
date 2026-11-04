import logging
import shutil
from collections.abc import Generator, Iterable, Iterator
from contextlib import closing, contextmanager
from pathlib import Path

from progress_bar import ProgressBarSource

from address_codec_jp.address import AddressCode, Prefecture
from address_codec_jp.database.cache.area_target import AreaTarget
from address_codec_jp.database.cache.directory import CacheDirectory
from address_codec_jp.database.cache.file_signature import DatabaseFileSignature
from address_codec_jp.database.cache.import_ledger import ImportLedger
from address_codec_jp.database.importing import AreaImporter, RegistryImporter
from address_codec_jp.datasets.address_base_registry import AbrDataset, DistributionScope
from address_codec_jp.datasets.download import (
    BoundaryDownloader,
    DistributedFile,
    RegistryDownloader,
)
from address_codec_jp.errors import DatabaseReplacedError
from address_codec_jp.results import AreaSource

_LOGGER: logging.Logger = logging.getLogger(__name__)


class CacheLoader:
    """
    Downloads registry files and area shapes and imports them into a cache directory.

    Every write holds the lock of the directory and downloads into a working directory
    that is removed afterwards. Files already imported, or known to be unpublished, are
    skipped without taking the lock. The area files of one dataset of a municipality are
    imported in one transaction, so that it is logged as imported only when all of them
    are. Additions on behalf of a codec name the file the codec opened, and are refused
    when the database has been replaced or removed since. Progress is logged at INFO
    level and, when a display is given, shown as one bar per step: the downloads, the
    imports of registry files, and the area datasets.

    Parameters
    ----------
    directory : CacheDirectory
        Directory whose database is built and extended.
    downloader : RegistryDownloader
        Downloader of the registry files.
    boundary_downloader : BoundaryDownloader
        Downloader of the census boundaries and registry maps.
    progress : ProgressBarSource | None
        Display that gets the bars, or ``None`` to show none.
    """

    def __init__(
        self,
        directory: CacheDirectory,
        downloader: RegistryDownloader,
        boundary_downloader: BoundaryDownloader,
        progress: ProgressBarSource | None = None,
    ) -> None:
        self._directory: CacheDirectory = directory
        self._downloader: RegistryDownloader = downloader
        self._boundary_downloader: BoundaryDownloader = boundary_downloader
        self._progress: ProgressBarSource | None = progress
        self._ledger: ImportLedger = ImportLedger()

    @property
    def directory(self) -> CacheDirectory:
        """
        Directory whose database is built and extended.

        Returns
        -------
        CacheDirectory
            The directory given at construction.
        """
        return self._directory

    def with_directory(self, directory: CacheDirectory) -> "CacheLoader":
        """
        Create a loader of another directory with the same downloaders and display.

        Parameters
        ----------
        directory : CacheDirectory
            Directory of the new loader.

        Returns
        -------
        CacheLoader
            Loader with an empty ledger.
        """
        return CacheLoader(directory, self._downloader, self._boundary_downloader, self._progress)

    def build(self) -> None:
        """
        Build the database with the town master and town points unless it exists.

        Raises
        ------
        RegistryDownloadError
            If a registry file cannot be downloaded.
        """
        database_path = self._directory.database_path
        with self._directory.locked():
            if database_path.is_file():
                return
            _LOGGER.info("Building the address database in %s.", database_path)
            working_directory = self._directory.make_working_directory()
            try:
                targets = [
                    target
                    for target in self._downloader.plan(Prefecture.list_codes())
                    if self.is_town_level(target)
                ]
                with self._report(targets, "Downloading registry files", "file") as reported:
                    paths = [
                        self._downloader.download(target, working_directory) for target in reported
                    ]
                working_path = working_directory / database_path.name
                with RegistryImporter.open(working_path) as importer:
                    _ = importer.import_files(paths, self._progress)
                _ = working_path.replace(database_path)
            finally:
                shutil.rmtree(working_directory, ignore_errors=True)
            _ = self._directory.remove_obsolete()
            _LOGGER.info("Built %s.", database_path)

    def add_registry_files(
        self, targets: list[DistributedFile], opened_file: DatabaseFileSignature | None = None
    ) -> None:
        """
        Import registry files unless they are imported or known to be unpublished.

        Parameters
        ----------
        targets : list[DistributedFile]
            Registry files to add; those the site does not distribute are remembered.
        opened_file : DatabaseFileSignature | None
            File a codec reads, or ``None`` when no codec waits for the files.

        Raises
        ------
        DatabaseReplacedError
            If the database is no longer ``opened_file``.
        RegistryDownloadError
            If a registry file cannot be downloaded.
        """
        database_path = self._directory.database_path
        self._check_opened_file(opened_file)
        self._ledger.read(database_path)
        if all(self._ledger.is_registry_file_settled(target.file_name) for target in targets):
            return
        with self._directory.locked():
            self._check_opened_file(opened_file)
            self._ledger.forget()
            self._ledger.read(database_path)
            pending = [
                target
                for target in targets
                if not self._ledger.is_registry_file_settled(target.file_name)
            ]
            if not pending:
                return
            _LOGGER.info("Adding %d registry files to %s.", len(pending), database_path)
            working_directory = self._directory.make_working_directory()
            try:
                with self._report(pending, "Downloading registry files", "file") as reported:
                    downloaded = [
                        self._downloader.download_if_distributed(target, working_directory)
                        for target in reported
                    ]
                paths = [path for path in downloaded if path is not None]
                if paths:
                    with RegistryImporter.open(database_path) as importer:
                        _ = importer.import_files(paths, self._progress)
                for target, path in zip(pending, downloaded, strict=True):
                    self._ledger.settle_registry_file(
                        target.file_name, is_published=path is not None
                    )
            finally:
                shutil.rmtree(working_directory, ignore_errors=True)

    def add_areas(
        self, targets: list[AreaTarget], opened_file: DatabaseFileSignature | None = None
    ) -> None:
        """
        Import area datasets unless they are imported or known to be unpublished.

        Each dataset is stored with all its files or not at all; the datasets imported
        before one that fails are kept.

        Parameters
        ----------
        targets : list[AreaTarget]
            Area datasets to add.
        opened_file : DatabaseFileSignature | None
            File a codec reads, or ``None`` when no codec waits for the shapes.

        Raises
        ------
        DatabaseReplacedError
            If the database is no longer ``opened_file``.
        RegistryDownloadError
            If a file cannot be downloaded.
        BoundaryFormatError
            If a downloaded file is malformed.
        """
        database_path = self._directory.database_path
        self._check_opened_file(opened_file)
        self._ledger.read(database_path)
        if all(self._ledger.is_area_settled(target) for target in targets):
            return
        with self._directory.locked():
            self._check_opened_file(opened_file)
            self._ledger.forget()
            self._ledger.read(database_path)
            pending = [target for target in targets if not self._ledger.is_area_settled(target)]
            if not pending:
                return
            _LOGGER.info("Adding %d area datasets to %s.", len(pending), database_path)
            working_directory = self._directory.make_working_directory()
            try:
                with (
                    AreaImporter.open(database_path) as importer,
                    self._report(pending, "Adding area datasets", "dataset") as reported,
                ):
                    for target in reported:
                        paths = self._download_areas(target, working_directory)
                        if paths:
                            _ = importer.import_files(paths, target.lg_code)
                        self._ledger.settle_area(target, is_published=bool(paths))
            finally:
                shutil.rmtree(working_directory, ignore_errors=True)

    def plan_lots(self, lg_codes: Iterable[str]) -> list[DistributedFile]:
        """
        Plan the block, residence, and land parcel files of municipalities.

        Parameters
        ----------
        lg_codes : Iterable[str]
            Six-digit local government codes; prefecture codes are skipped.

        Returns
        -------
        list[DistributedFile]
            Registry files of the municipalities.
        """
        municipality_codes = sorted(
            {lg_code for lg_code in lg_codes if not AddressCode.is_prefecture_code(lg_code)}
        )
        return self._downloader.plan_lots(municipality_codes)

    def plan_areas(self, lg_codes: Iterable[str], *, is_parcel_included: bool) -> list[AreaTarget]:
        """
        Plan the town boundaries, and optionally the land parcel maps, of municipalities.

        Parameters
        ----------
        lg_codes : Iterable[str]
            Six-digit local government codes; prefecture codes are skipped.
        is_parcel_included : bool
            Whether the land parcel maps are planned besides the town boundaries.

        Returns
        -------
        list[AreaTarget]
            Area datasets ordered by municipality.

        Raises
        ------
        ValueError
            If a code is malformed.
        """
        sources = [
            AreaSource.CENSUS_BOUNDARY,
            *([AreaSource.REGISTRY_MAP] if is_parcel_included else []),
        ]
        return [
            AreaTarget(source, lg_code)
            for lg_code in sorted(set(lg_codes))
            if not AddressCode.is_prefecture_code(AddressCode(lg_code=lg_code).lg_code)
            for source in sources
        ]

    def reset(self) -> None:
        """Forget what the ledger knows, including the unpublished files."""
        self._ledger.reset()

    def is_town_level(self, target: DistributedFile) -> bool:
        """
        Tell whether a registry file belongs to the database built first.

        Parameters
        ----------
        target : DistributedFile
            Registry file.

        Returns
        -------
        bool
            ``True`` for nationwide files and the town points.
        """
        return (
            target.dataset.scope is DistributionScope.NATIONWIDE
            or target.dataset is AbrDataset.TOWN_POSITION
        )

    def _check_opened_file(self, opened_file: DatabaseFileSignature | None) -> None:
        if opened_file is None:
            return
        current = DatabaseFileSignature.of(self._directory.database_path)
        if current is None or not opened_file.is_same_file(current):
            raise DatabaseReplacedError(
                f"The address database {self._directory.database_path} was replaced or "
                + "removed after the codec opened it, such as by DatabaseCache.refresh or "
                + "clear; close the codec and open it again."
            )

    @contextmanager
    def _report[ItemT](
        self, items: list[ItemT], description: str, unit: str
    ) -> Generator[Iterator[ItemT]]:
        if self._progress is None:
            yield iter(items)
            return
        with closing(self._progress.report(items, description=description, unit=unit)) as reported:
            yield reported

    def _download_areas(self, target: AreaTarget, directory: Path) -> list[Path]:
        match target.source:
            case AreaSource.CENSUS_BOUNDARY:
                path = self._boundary_downloader.download_census_boundary(target.lg_code, directory)
                return [] if path is None else [path]
            case AreaSource.REGISTRY_MAP:
                return self._boundary_downloader.download_registry_maps(target.lg_code, directory)
