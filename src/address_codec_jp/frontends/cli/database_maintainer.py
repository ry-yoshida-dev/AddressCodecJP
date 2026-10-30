import sys
from pathlib import Path

from address_codec_jp.address_codec import AddressCodec
from address_codec_jp.database.cache import DatabaseCache
from address_codec_jp.database.importing import AreaImporter, RegistryImporter
from address_codec_jp.datasets.address_base_registry import ImportSummary
from address_codec_jp.datasets.download import RegistryDownloader
from address_codec_jp.frontends.cli.cache_action import CacheAction
from address_codec_jp.frontends.cli.command_arguments import CommandArguments


class DatabaseMaintainer:
    """Runs the commands that fill, describe, and manage address databases."""

    def manage_cache(self, cache: DatabaseCache, namespace: CommandArguments) -> None:
        """
        Run the action of the ``cache`` command.

        Parameters
        ----------
        cache : DatabaseCache
            Default cache.
        namespace : CommandArguments
            Parsed options of the command.
        """
        match namespace.cache_action:
            case CacheAction.INFO:
                status = cache.describe()
                built_at = (
                    "" if status.built_at is None else status.built_at.isoformat(timespec="seconds")
                )
                rows = [
                    ("path", str(status.path)),
                    ("built_at", built_at),
                    ("size_mb", f"{status.size_bytes / 1_000_000:.1f}"),
                    ("registry_files", str(status.registry_file_count)),
                    ("lot_municipalities", str(len(status.lot_municipality_codes))),
                    ("boundary_municipalities", str(len(status.boundary_municipality_codes))),
                    ("parcel_map_municipalities", str(len(status.parcel_map_municipality_codes))),
                    ("obsolete_files", str(len(status.obsolete_paths))),
                ]
                for name, value in rows:
                    print(f"{name}\t{value}")
            case CacheAction.CLEAR:
                for path in cache.clear():
                    print(f"Removed {path}")
            case CacheAction.REFRESH:
                print(f"Downloading everything {cache.path} holds again.", file=sys.stderr)
                cache.refresh()
                print(f"Refreshed {cache.path}")
            case CacheAction.PREPARE:
                cache.prepare(
                    namespace.prefectures,
                    namespace.municipalities,
                    is_area_included=not namespace.is_area_excluded,
                    is_parcel_included=namespace.is_parcel_included,
                )
                print(f"Prepared {cache.path}")

    def import_registry_files(self, database_path: Path, sources: list[Path]) -> None:
        """
        Import registry files and report their rows.

        Parameters
        ----------
        database_path : Path
            Database to import into.
        sources : list[Path]
            Registry CSV files or their ZIP archives.
        """
        with RegistryImporter.open(database_path) as importer:
            for summary in importer.import_files(sources):
                self._report(summary)

    def _report(self, summary: ImportSummary) -> None:
        complemented = (
            f", added {summary.complemented_count} oaza-level towns"
            if summary.complemented_count
            else ""
        )
        print(
            f"Imported {summary.stored_count} rows of {summary.dataset.value} from "
            + f"{summary.source}{complemented}; removed {summary.removed_count} rows."
        )

    def download(self, namespace: CommandArguments, database_path: Path) -> None:
        """
        Download registry files, and import them when asked.

        Parameters
        ----------
        namespace : CommandArguments
            Parsed options of the ``download`` command.
        database_path : Path
            Database to import into with ``--import``.
        """
        downloader = RegistryDownloader(namespace.base_url)
        directory = Path(namespace.directory)
        paths: list[Path] = []
        for target in downloader.plan(namespace.prefectures, namespace.municipalities):
            path = downloader.download(
                target, directory, is_existing_kept=namespace.is_existing_kept
            )
            print(f"Downloaded {downloader.url_of(target)} to {path}")
            paths.append(path)
        if namespace.is_imported:
            self.import_registry_files(database_path, paths)

    def import_areas(self, database_path: Path, sources: list[Path], lg_code: str) -> None:
        """
        Import census boundary or registry map files of one municipality.

        Parameters
        ----------
        database_path : Path
            Database to import into.
        sources : list[Path]
            Census boundary ZIP archives or registry map archives.
        lg_code : str
            Six-digit local government code of the municipality the files cover.
        """
        with AreaImporter.open(database_path) as area_importer:
            for source in sources:
                area_import = area_importer.import_file(source, lg_code)
                print(
                    f"Imported {area_import.stored_count} shapes of "
                    + f"{area_import.source.value} from {source}; "
                    + f"{area_import.unmatched_count} matched no address."
                )

    def print_imports(self, database_path: Path) -> None:
        """
        List the imported registry and area files as tab-separated lines.

        Parameters
        ----------
        database_path : Path
            Database to describe.
        """
        with AddressCodec.open(database_path) as codec:
            for dataset_import in codec.list_imports():
                print(
                    "\t".join(
                        [
                            dataset_import.imported_at.isoformat(timespec="seconds"),
                            dataset_import.dataset.value,
                            str(dataset_import.row_count),
                            dataset_import.source_name,
                            dataset_import.source_sha256,
                        ]
                    )
                )
            for area_import in codec.list_area_imports():
                print(
                    "\t".join(
                        [
                            area_import.imported_at.isoformat(timespec="seconds"),
                            area_import.source.value,
                            str(area_import.stored_count),
                            area_import.source_name,
                            area_import.source_sha256,
                        ]
                    )
                )
