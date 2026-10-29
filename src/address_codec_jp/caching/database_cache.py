import logging
import os
import shutil
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import ClassVar, Self

import platformdirs

from address_codec_jp.area_importer import AreaImporter
from address_codec_jp.caching.area_target import AreaTarget
from address_codec_jp.caching.cache_directory import CacheDirectory
from address_codec_jp.caching.cache_status import CacheStatus
from address_codec_jp.caching.import_ledger import ImportLedger
from address_codec_jp.domain.address_code import AddressCode
from address_codec_jp.domain.area_source import AreaSource
from address_codec_jp.domain.prefecture import Prefecture
from address_codec_jp.download.boundary_downloader import BoundaryDownloader
from address_codec_jp.download.distributed_file import DistributedFile
from address_codec_jp.download.registry_downloader import RegistryDownloader
from address_codec_jp.errors.boundary_format_error import BoundaryFormatError
from address_codec_jp.errors.dataset_not_imported_error import DatasetNotImportedError
from address_codec_jp.errors.registry_download_error import RegistryDownloadError
from address_codec_jp.registry.abr_dataset import AbrDataset
from address_codec_jp.registry.distribution_scope import DistributionScope
from address_codec_jp.registry_importer import RegistryImporter
from address_codec_jp.storage.address_database import AddressDatabase
from address_codec_jp.storage.area_import import AreaImport

_LOGGER: logging.Logger = logging.getLogger(__name__)


class DatabaseCache:
    """
    Address database built on first use from the registry download site.

    The database is first built with the nationwide town master and the representative
    points of all prefectures, municipalities, and towns, which takes about 15 MB of
    downloads and 180 MB on disk. Blocks, residences, and land parcels are added by
    ``ensure_lots`` when an area needs them, from the residence indication and land
    parcel files of its municipality, and town boundaries and land parcel maps by
    ``ensure_areas``. ``prepare`` adds them ahead of time, e.g. while building a container
    image, and with ``is_download_allowed=False`` nothing is downloaded on use, so that a
    service answers from what was prepared and never waits for the network.

    Each schema version has its own file, so a new version of the library builds a new
    database instead of failing on an old one; the files of older versions are removed
    when a new one is built. The database is built in a temporary directory and moved
    into place when complete, so an interrupted build never leaves a partial database.
    Writes are serialized across processes by a lock file in the directory, so that the
    workers of a server can share one cache. Progress is logged to the
    ``address_codec_jp.caching.database_cache`` logger at INFO level.

    Parameters
    ----------
    directory : Path
        Directory that holds the database.
    downloader : RegistryDownloader
        Downloader of the registry files.
    boundary_downloader : BoundaryDownloader
        Downloader of the census boundaries and registry maps.
    is_download_allowed : bool
        Whether ``ensure``, ``ensure_lots``, and ``ensure_areas`` may download. When not,
        a missing database raises ``DatasetNotImportedError`` and missing points and
        shapes are left out, so that lookups fall back to the enclosing areas.
    max_age : timedelta | None
        Age after which ``ensure`` refreshes the database before its first use by this
        cache, or ``None`` to keep it until ``refresh`` is called. A refresh that fails
        is logged as a warning and the current database stays in use.

    Raises
    ------
    ValueError
        If ``max_age`` is not positive.

    Examples
    --------
    Prepare Tokyo while building an image, then serve without downloads:

    >>> DatabaseCache.default().prepare(prefecture_codes=["13"])  # doctest: +SKIP
    >>> cache = DatabaseCache.default(is_download_allowed=False)  # doctest: +SKIP
    >>> with AddressCodec.open(cache=cache) as codec:  # doctest: +SKIP
    ...     codec.locate("千代田区丸の内1-9-1")
    """

    DIRECTORY_VARIABLE: ClassVar[str] = "ADDRESS_CODEC_JP_CACHE_DIR"
    BASE_URL_VARIABLE: ClassVar[str] = "ADDRESS_CODEC_JP_BASE_URL"
    CENSUS_URL_VARIABLE: ClassVar[str] = "ADDRESS_CODEC_JP_CENSUS_URL"
    CATALOG_URL_VARIABLE: ClassVar[str] = "ADDRESS_CODEC_JP_CATALOG_URL"
    _APPLICATION_NAME: ClassVar[str] = "address-codec-jp"

    def __init__(
        self,
        directory: Path,
        downloader: RegistryDownloader,
        boundary_downloader: BoundaryDownloader,
        *,
        is_download_allowed: bool = True,
        max_age: timedelta | None = None,
    ) -> None:
        if max_age is not None and max_age <= timedelta(0):
            raise ValueError(f"max_age must be positive, got {max_age}.")
        self._directory: CacheDirectory = CacheDirectory(directory)
        self._downloader: RegistryDownloader = downloader
        self._boundary_downloader: BoundaryDownloader = boundary_downloader
        self._is_download_allowed: bool = is_download_allowed
        self._max_age: timedelta | None = max_age
        self._ledger: ImportLedger = ImportLedger()
        self._is_age_checked: bool = False

    @classmethod
    def default(
        cls,
        *,
        directory: Path | None = None,
        is_download_allowed: bool = True,
        max_age: timedelta | None = None,
    ) -> Self:
        """
        Create the cache in the configured directory, downloading from the official sites.

        ``ADDRESS_CODEC_JP_CACHE_DIR`` names the directory when ``directory`` is not
        given, the user cache directory of the platform by default.
        ``ADDRESS_CODEC_JP_BASE_URL`` names the registry download site or a mirror, and
        ``ADDRESS_CODEC_JP_CENSUS_URL`` and ``ADDRESS_CODEC_JP_CATALOG_URL`` replace the
        URL templates of ``BoundaryDownloader``.

        Parameters
        ----------
        directory : Path | None
            Directory of the cache, or ``None`` for the configured one.
        is_download_allowed : bool
            Whether data may be downloaded on use.
        max_age : timedelta | None
            Age after which the database is refreshed on first use, or ``None``.

        Returns
        -------
        Self
            Cache in the directory.

        Raises
        ------
        ValueError
            If ``max_age`` is not positive.
        """
        configured_directory = os.environ.get(cls.DIRECTORY_VARIABLE, "")
        if directory is not None:
            cache_directory = directory
        elif configured_directory:
            cache_directory = Path(configured_directory)
        else:
            cache_directory = platformdirs.user_cache_path(cls._APPLICATION_NAME)
        base_url = os.environ.get(cls.BASE_URL_VARIABLE, "") or RegistryDownloader.DEFAULT_BASE_URL
        census_url = (
            os.environ.get(cls.CENSUS_URL_VARIABLE, "")
            or BoundaryDownloader.DEFAULT_CENSUS_URL_TEMPLATE
        )
        catalog_url = (
            os.environ.get(cls.CATALOG_URL_VARIABLE, "")
            or BoundaryDownloader.DEFAULT_CATALOG_URL_TEMPLATE
        )
        return cls(
            cache_directory,
            RegistryDownloader(base_url),
            BoundaryDownloader(census_url, catalog_url),
            is_download_allowed=is_download_allowed,
            max_age=max_age,
        )

    @property
    def path(self) -> Path:
        """
        Path of the database of the current schema version.

        Returns
        -------
        Path
            File such as ``towns-v4.sqlite3`` in the cache directory.
        """
        return self._directory.database_path

    @property
    def is_built(self) -> bool:
        """
        Tell whether the database has been built.

        Returns
        -------
        bool
            ``True`` when the database file exists.
        """
        return self.path.is_file()

    @property
    def is_download_allowed(self) -> bool:
        """
        Tell whether data may be downloaded on use.

        Returns
        -------
        bool
            The value given at construction.
        """
        return self._is_download_allowed

    def ensure(self) -> Path:
        """
        Build the database unless it has been built, and refresh it once when too old.

        Returns
        -------
        Path
            Path of the database.

        Raises
        ------
        DatasetNotImportedError
            If the database has not been built and downloads are not allowed.
        RegistryDownloadError
            If a registry file cannot be downloaded while building.
        """
        if not self.is_built:
            if not self._is_download_allowed:
                raise DatasetNotImportedError(
                    f"The address database {self.path} has not been built and downloads "
                    + "are not allowed; call DatabaseCache.prepare first."
                )
            self._build()
        elif not self._is_age_checked:
            self._is_age_checked = True
            if self._is_download_allowed and self._is_expired():
                self._refresh_expired()
        return self.path

    def ensure_lots(self, lg_codes: Iterable[str]) -> None:
        """
        Add the blocks, residences, and land parcels of some areas unless already added.

        Nothing is downloaded when downloads are not allowed.

        Parameters
        ----------
        lg_codes : Iterable[str]
            Six-digit local government codes; prefecture codes are skipped, and the
            files of a municipality that the site does not distribute are skipped too.

        Raises
        ------
        ValueError
            If a code is malformed.
        DatasetNotImportedError
            If the database has not been built and downloads are not allowed.
        RegistryDownloadError
            If a registry file cannot be downloaded.
        """
        database_path = self.ensure()
        if self._is_download_allowed:
            self._add_registry_files(database_path, self._plan_lots(lg_codes))

    def ensure_areas(self, lg_codes: Iterable[str], *, is_parcel_included: bool) -> None:
        """
        Add the town boundaries, and optionally the land parcel maps, of municipalities.

        Nothing is downloaded when downloads are not allowed.

        Parameters
        ----------
        lg_codes : Iterable[str]
            Six-digit local government codes; prefecture codes are skipped.
        is_parcel_included : bool
            Whether the land parcel maps are added besides the town boundaries.

        Raises
        ------
        ValueError
            If a code is malformed.
        DatasetNotImportedError
            If the database has not been built and downloads are not allowed.
        RegistryDownloadError
            If a file cannot be downloaded.
        BoundaryFormatError
            If a downloaded file is malformed.
        """
        database_path = self.ensure()
        if self._is_download_allowed:
            self._add_areas(
                database_path, self._plan_areas(lg_codes, is_parcel_included=is_parcel_included)
            )

    def prepare(
        self,
        prefecture_codes: Sequence[str] = (),
        municipality_codes: Sequence[str] = (),
        *,
        is_area_included: bool = True,
        is_parcel_included: bool = False,
    ) -> None:
        """
        Download the data of whole prefectures or municipalities ahead of use.

        Builds the database if needed and adds the blocks, residences, and land parcel
        points of every municipality of the areas, and optionally their shapes. Downloads
        happen even when they are not allowed on use.

        Parameters
        ----------
        prefecture_codes : Sequence[str]
            Two-digit codes of prefectures whose municipalities are prepared.
        municipality_codes : Sequence[str]
            Six-digit local government codes of further municipalities.
        is_area_included : bool
            Whether the census town boundaries are added.
        is_parcel_included : bool
            Whether the registry maps are added; tens of megabytes per municipality.

        Raises
        ------
        ValueError
            If a code is malformed.
        RegistryDownloadError
            If a file cannot be downloaded.
        BoundaryFormatError
            If a downloaded area file is malformed.
        """
        for prefecture_code in prefecture_codes:
            if not Prefecture.is_code(prefecture_code):
                raise ValueError(f"Prefecture code must be 01 to 47, got {prefecture_code!r}.")
        lg_codes = [AddressCode(lg_code=code).lg_code for code in municipality_codes]
        if not self.is_built:
            self._build()
        database_path = self.path
        with AddressDatabase.open_read_only(database_path) as database:
            lg_codes.extend(
                municipality.lg_code
                for municipality in database.towns.list_municipalities()
                if municipality.lg_code[:2] in prefecture_codes
            )
        _LOGGER.info("Preparing %d municipalities in %s.", len(set(lg_codes)), database_path)
        self._add_registry_files(database_path, self._plan_lots(lg_codes))
        if is_area_included or is_parcel_included:
            self._add_areas(
                database_path,
                [
                    target
                    for target in self._plan_areas(lg_codes, is_parcel_included=is_parcel_included)
                    if is_area_included or target.source is AreaSource.REGISTRY_MAP
                ],
            )

    def describe(self) -> CacheStatus:
        """
        Summarize what the database holds.

        Returns
        -------
        CacheStatus
            Path, size, build time, the municipalities added on demand, and obsolete
            files.
        """
        obsolete_paths = tuple(self._directory.list_obsolete())
        if not self.is_built:
            return CacheStatus(
                path=self.path,
                is_built=False,
                size_bytes=0,
                built_at=None,
                registry_file_count=0,
                lot_municipality_codes=(),
                boundary_municipality_codes=(),
                parcel_map_municipality_codes=(),
                obsolete_paths=obsolete_paths,
            )
        with AddressDatabase.open_read_only(self.path) as database:
            dataset_imports = database.imports.list_all()
            area_imports = database.areas.list_imports()
        lot_codes = {
            registry_file.area_code
            for registry_file in (
                DistributedFile.from_file_name(item.source_name) for item in dataset_imports
            )
            if registry_file is not None
            and registry_file.area_code is not None
            and registry_file.scope is DistributionScope.MUNICIPALITY
        }
        return CacheStatus(
            path=self.path,
            is_built=True,
            size_bytes=self.path.stat().st_size,
            built_at=min((item.imported_at for item in dataset_imports), default=None),
            registry_file_count=len(dataset_imports),
            lot_municipality_codes=tuple(sorted(lot_codes)),
            boundary_municipality_codes=self._area_codes(area_imports, AreaSource.CENSUS_BOUNDARY),
            parcel_map_municipality_codes=self._area_codes(area_imports, AreaSource.REGISTRY_MAP),
            obsolete_paths=obsolete_paths,
        )

    def refresh(self) -> None:
        """
        Download again everything the database holds and replace it when complete.

        The town master and town points are rebuilt, and the registry files and area
        shapes of every municipality added so far are added again, so that the cache
        follows the latest releases. Downloads happen even when they are not allowed on
        use. The current database stays in use until the new one is complete; codecs
        opened before keep reading the old one until they are closed.

        Raises
        ------
        RegistryDownloadError
            If a file cannot be downloaded; the current database is kept then.
        BoundaryFormatError
            If a downloaded area file is malformed; the current database is kept then.
        """
        with self._directory.locked():
            if not self.is_built:
                self._build()
                return
            _LOGGER.info("Refreshing %s.", self.path)
            with AddressDatabase.open_read_only(self.path) as database:
                registry_files = [
                    DistributedFile.from_file_name(item.source_name)
                    for item in database.imports.list_all()
                ]
                area_targets = sorted(
                    {
                        AreaTarget(item.source, item.lg_code)
                        for item in database.areas.list_imports()
                    },
                    key=lambda target: (target.source.value, target.lg_code),
                )
            staging_directory = self._directory.make_working_directory()
            try:
                staging = type(self)(staging_directory, self._downloader, self._boundary_downloader)
                staging._build()
                staging._add_registry_files(
                    staging.path,
                    [
                        registry_file
                        for registry_file in registry_files
                        if registry_file is not None and not self._is_town_level(registry_file)
                    ],
                )
                staging._add_areas(staging.path, area_targets)
                _ = staging.path.replace(self.path)
            finally:
                shutil.rmtree(staging_directory, ignore_errors=True)
            self._ledger.reset()
            _LOGGER.info("Refreshed %s.", self.path)

    def clear(self) -> list[Path]:
        """
        Delete the database and the obsolete files of the cache directory.

        Returns
        -------
        list[Path]
            Deleted files and directories.
        """
        if not self._directory.root.is_dir():
            return []
        with self._directory.locked():
            removed = [*self._directory.remove_obsolete(), *self._directory.remove_database()]
            self._ledger.reset()
        return removed

    def remove_obsolete(self) -> list[Path]:
        """
        Delete databases of older schema versions and leftovers of interrupted builds.

        Working directories younger than ``CacheDirectory.STALE_WORKING_SECONDS`` are
        kept, because another process may still be building in them, and so are
        databases of newer schema versions, which a newer library may be using.

        Returns
        -------
        list[Path]
            Deleted files and directories.
        """
        return self._directory.remove_obsolete()

    def _build(self) -> None:
        with self._directory.locked():
            if self.is_built:
                return
            _LOGGER.info("Building the address database in %s.", self.path)
            working_directory = self._directory.make_working_directory()
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
            _ = self._directory.remove_obsolete()
            _LOGGER.info("Built %s.", self.path)

    def _is_expired(self) -> bool:
        if self._max_age is None:
            return False
        with AddressDatabase.open_read_only(self.path) as database:
            imported_times = [item.imported_at for item in database.imports.list_all()]
        built_at = min(imported_times, default=None)
        return built_at is None or datetime.now(UTC) - built_at > self._max_age

    def _refresh_expired(self) -> None:
        try:
            self.refresh()
        except (RegistryDownloadError, BoundaryFormatError) as error:
            _LOGGER.warning("Could not refresh %s; using it as it is: %s", self.path, error)

    def _add_registry_files(self, database_path: Path, targets: list[DistributedFile]) -> None:
        self._ledger.read(database_path)
        if all(self._ledger.is_registry_file_settled(target.file_name) for target in targets):
            return
        with self._directory.locked():
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
                downloaded = [
                    self._downloader.download_if_distributed(target, working_directory)
                    for target in pending
                ]
                paths = [path for path in downloaded if path is not None]
                if paths:
                    with RegistryImporter.open(database_path) as importer:
                        _ = importer.import_files(paths)
                for target, path in zip(pending, downloaded, strict=True):
                    self._ledger.settle_registry_file(
                        target.file_name, is_published=path is not None
                    )
            finally:
                shutil.rmtree(working_directory, ignore_errors=True)

    def _add_areas(self, database_path: Path, targets: list[AreaTarget]) -> None:
        self._ledger.read(database_path)
        if all(self._ledger.is_area_settled(target) for target in targets):
            return
        with self._directory.locked():
            self._ledger.forget()
            self._ledger.read(database_path)
            pending = [target for target in targets if not self._ledger.is_area_settled(target)]
            if not pending:
                return
            _LOGGER.info("Adding %d area datasets to %s.", len(pending), database_path)
            working_directory = self._directory.make_working_directory()
            try:
                with AreaImporter.open(database_path) as importer:
                    for target in pending:
                        paths = self._download_areas(target, working_directory)
                        for path in paths:
                            _ = importer.import_file(path, target.lg_code)
                        self._ledger.settle_area(target, is_published=bool(paths))
            finally:
                shutil.rmtree(working_directory, ignore_errors=True)

    def _download_areas(self, target: AreaTarget, directory: Path) -> list[Path]:
        match target.source:
            case AreaSource.CENSUS_BOUNDARY:
                path = self._boundary_downloader.download_census_boundary(target.lg_code, directory)
                return [] if path is None else [path]
            case AreaSource.REGISTRY_MAP:
                return self._boundary_downloader.download_registry_maps(target.lg_code, directory)

    def _area_codes(self, area_imports: list[AreaImport], source: AreaSource) -> tuple[str, ...]:
        return tuple(sorted({item.lg_code for item in area_imports if item.source is source}))

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

    def _plan_areas(self, lg_codes: Iterable[str], *, is_parcel_included: bool) -> list[AreaTarget]:
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

    def _is_town_level(self, target: DistributedFile) -> bool:
        return (
            target.dataset.scope is DistributionScope.NATIONWIDE
            or target.dataset is AbrDataset.TOWN_POSITION
        )
