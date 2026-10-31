import logging
import os
import sqlite3
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

import pytest
from geo_coordinate import GeoCoordinate

from address_codec_jp import (
    AbrDataset,
    AddressCodec,
    AddressDatabase,
    AddressLevel,
    BoundaryDownloader,
    DatabaseCache,
    DatabaseReplacedError,
    DatasetNotImportedError,
    DistributedFile,
    DistributionScope,
    RegistryDownloader,
    RegistryDownloadError,
)
from address_codec_jp.database.cache import CacheDirectory, CacheLoader
from address_codec_jp.frontends.cli import CommandLineInterface
from tests.fixture_paths import FIXTURE_DIRECTORY

FIXTURE_NAMES: dict[AbrDataset, str] = {
    AbrDataset.TOWN: "mt_town_sample.csv",
    AbrDataset.PREFECTURE_POSITION: "positions/mt_pref_pos_sample.csv",
    AbrDataset.MUNICIPALITY_POSITION: "positions/mt_city_pos_sample.csv",
    AbrDataset.TOWN_POSITION: "positions/mt_town_pos_sample.csv",
    AbrDataset.BLOCK: "positions/mt_rsdtdsp_blk_sample.csv",
    AbrDataset.BLOCK_POSITION: "positions/mt_rsdtdsp_blk_pos_sample.csv",
    AbrDataset.RESIDENCE: "positions/mt_rsdtdsp_rsdt_sample.csv",
    AbrDataset.RESIDENCE_POSITION: "positions/mt_rsdtdsp_rsdt_pos_sample.csv",
    AbrDataset.PARCEL: "positions/mt_parcel_sample.csv",
    AbrDataset.PARCEL_POSITION: "positions/mt_parcel_pos_sample.csv",
}
TOWN_LEVEL_DATASETS: set[AbrDataset] = {
    AbrDataset.TOWN,
    AbrDataset.PREFECTURE_POSITION,
    AbrDataset.MUNICIPALITY_POSITION,
    AbrDataset.TOWN_POSITION,
}
TOKYO_STATION: GeoCoordinate = GeoCoordinate.from_degrees(35.6812, 139.7671)


@pytest.fixture
def mirror(tmp_path: Path) -> Path:
    """Build a mirror serving town-level files and the lots of Chiyoda and Miyoshi."""
    root = tmp_path / "mirror"
    downloader = RegistryDownloader()
    prefecture_codes = [f"{number:02d}" for number in range(1, 48)]
    town_level = [
        target
        for target in downloader.plan(prefecture_codes)
        if target.dataset in TOWN_LEVEL_DATASETS
    ]
    lots = [
        target
        for target in downloader.plan_lots(["131016", "113247"])
        if not (
            target.area_code == "131016" and target.dataset.scope is DistributionScope.MUNICIPALITY
        )
    ]
    for target in [*town_level, *lots]:
        archive_path = root / target.url_path
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.write(FIXTURE_DIRECTORY / FIXTURE_NAMES[target.dataset], "data.csv")
    return root


@pytest.fixture
def cache(mirror: Path, tmp_path: Path) -> DatabaseCache:
    """Provide a cache in a temporary directory that downloads from ``mirror``."""
    return DatabaseCache(
        tmp_path / "cache", RegistryDownloader(mirror.as_uri()), BoundaryDownloader()
    )


def test_ensure_builds_the_town_level_database(cache: DatabaseCache) -> None:
    assert not cache.is_built
    path = cache.ensure()
    assert path == cache.path
    assert path.name == f"towns-v{AddressDatabase.SCHEMA_VERSION}.sqlite3"
    assert cache_files(cache) == [path.name]
    with AddressCodec.open(path) as codec:
        assert str(codec.encode("千代田区丸の内1-2-3")) == "131016-0011001-2-3"
        assert codec.locate("千代田区丸の内1-2-3").level is AddressLevel.TOWN
        datasets = {dataset_import.dataset for dataset_import in codec.list_imports()}
    assert datasets == TOWN_LEVEL_DATASETS


def test_ensure_reuses_a_built_database(cache: DatabaseCache, mirror: Path) -> None:
    path = cache.ensure()
    modified_at = path.stat().st_mtime_ns
    (mirror / "mt_town" / "mt_town_all.csv.zip").unlink()
    assert cache.ensure() == path
    assert path.stat().st_mtime_ns == modified_at


def test_failed_build_leaves_nothing(cache: DatabaseCache, mirror: Path) -> None:
    (mirror / "mt_town_pos" / "pref" / "mt_town_pos_pref47.csv.zip").unlink()
    with pytest.raises(RegistryDownloadError, match="mt_town_pos_pref47"):
        _ = cache.ensure()
    assert not cache.is_built
    assert cache_files(cache) == []


def test_default_uses_the_configured_directory_and_site(
    mirror: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(DatabaseCache.DIRECTORY_VARIABLE, str(tmp_path / "configured"))
    monkeypatch.setenv(DatabaseCache.BASE_URL_VARIABLE, mirror.as_uri())
    cache = DatabaseCache.default()
    assert cache.ensure().parent == tmp_path / "configured"


def test_open_and_cli_default_to_the_cached_database(
    cache: DatabaseCache,
    mirror: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _ = cache.ensure()
    monkeypatch.setenv(DatabaseCache.DIRECTORY_VARIABLE, str(cache.path.parent))
    monkeypatch.setenv(DatabaseCache.BASE_URL_VARIABLE, mirror.as_uri())
    with AddressCodec.open() as codec:
        assert str(codec.encode("千代田区丸の内1-2-3")) == "131016-0011001-2-3"
        assert codec.locate("千代田区丸の内1-2-3").level is AddressLevel.RESIDENCE
    assert CommandLineInterface().run(["encode", "千代田区丸の内1-2-3"]) == 0
    captured = capsys.readouterr()
    assert captured.out.splitlines() == ["千代田区丸の内1-2-3\t131016-0011001-2-3"]
    assert captured.err == ""


def cache_files(cache: DatabaseCache) -> list[str]:
    return sorted(path.name for path in cache.path.parent.iterdir() if path.name != "cache.lock")


def imported_names(cache: DatabaseCache) -> list[str]:
    with AddressCodec.open(cache.path) as codec:
        return [dataset_import.source_name for dataset_import in codec.list_imports()]


def test_ensure_lots_adds_the_prefecture_and_municipality_files(cache: DatabaseCache) -> None:
    cache.ensure_lots(["113247"])
    names = imported_names(cache)
    assert "mt_rsdtdsp_rsdt_pos_city113247.csv.zip" in names
    assert "mt_parcel_pos_city113247.csv.zip" in names
    with AddressCodec(AddressDatabase.open_read_only(cache.path), cache) as codec:
        location = codec.locate("三芳町竹間沢123-4")
        assert location.level is AddressLevel.RESIDENCE
        assert location.is_exact


def test_locate_adds_lots_on_demand(cache: DatabaseCache) -> None:
    with AddressCodec(AddressDatabase.open_read_only(cache.ensure()), cache) as codec:
        assert codec.locate("千代田区丸の内1").level is AddressLevel.TOWN
        assert not any("rsdtdsp" in name for name in imported_names(cache))
        location = codec.locate("千代田区丸の内1-2-3")
        assert location.located_code == location.code
        assert codec.encode("千代田区丸の内1-2-3", is_lot_verified=True) == location.code
    assert "mt_rsdtdsp_rsdt_pos_city131016.csv.zip" in imported_names(cache)


def test_find_nearest_adds_lots_of_nearby_municipalities(cache: DatabaseCache) -> None:
    with AddressCodec(AddressDatabase.open_read_only(cache.ensure()), cache) as codec:
        nearest = codec.find_nearest(TOKYO_STATION)
    assert nearest.code.level in {AddressLevel.BLOCK, AddressLevel.RESIDENCE}


def test_added_lots_are_not_downloaded_again(cache: DatabaseCache, mirror: Path) -> None:
    cache.ensure_lots(["131016"])
    count = len(imported_names(cache))
    for archive in mirror.rglob("*.zip"):
        archive.unlink()
    cache.ensure_lots(["131016"])
    DatabaseCache(
        cache.path.parent, RegistryDownloader(mirror.as_uri()), BoundaryDownloader()
    ).ensure_lots(["131016"])
    assert len(imported_names(cache)) == count


def test_download_if_distributed_skips_missing_files(mirror: Path, tmp_path: Path) -> None:
    downloader = RegistryDownloader(mirror.as_uri())
    missing = DistributedFile(AbrDataset.PARCEL, "131016")
    assert downloader.download_if_distributed(missing, tmp_path / "data") is None
    with pytest.raises(RegistryDownloadError):
        _ = downloader.download(missing, tmp_path / "data")


def test_plan_lots_lists_residence_and_parcel_files_per_municipality() -> None:
    names = [target.file_name for target in RegistryDownloader().plan_lots(["131016"])]
    assert names == [
        "mt_rsdtdsp_blk_city131016.csv.zip",
        "mt_rsdtdsp_blk_pos_city131016.csv.zip",
        "mt_rsdtdsp_rsdt_city131016.csv.zip",
        "mt_rsdtdsp_rsdt_pos_city131016.csv.zip",
        "mt_parcel_city131016.csv.zip",
        "mt_parcel_pos_city131016.csv.zip",
    ]


def test_describe_lists_what_the_cache_holds(cache: DatabaseCache) -> None:
    assert not cache.describe().is_built
    cache.ensure_lots(["113247"])
    status = cache.describe()
    assert status.is_built
    assert status.path == cache.path
    assert status.size_bytes == cache.path.stat().st_size
    assert status.built_at is not None
    assert status.lot_municipality_codes == ("113247",)
    assert status.boundary_municipality_codes == ()
    assert status.obsolete_paths == ()


def test_build_removes_obsolete_files(cache: DatabaseCache) -> None:
    directory = cache.path.parent
    directory.mkdir(parents=True)
    old_database = directory / "towns-v1.sqlite3"
    _ = old_database.write_bytes(b"old")
    stale = directory / "build-stale"
    stale.mkdir()
    (stale / ".address-codec-jp-build").touch()
    old_time = time.time() - 2 * CacheDirectory.STALE_WORKING_SECONDS
    os.utime(stale, (old_time, old_time))
    running = directory / "build-running"
    running.mkdir()
    newer_database = directory / f"towns-v{AddressDatabase.SCHEMA_VERSION + 1}.sqlite3"
    _ = newer_database.write_bytes(b"newer")
    assert cache.describe().obsolete_paths == (stale, old_database)
    _ = cache.ensure()
    assert cache_files(cache) == ["build-running", cache.path.name, newer_database.name]


def test_clear_deletes_the_database(cache: DatabaseCache) -> None:
    path = cache.ensure()
    assert cache.clear() == [path]
    assert not cache.is_built
    assert cache.clear() == []


def test_files_of_others_in_the_directory_are_kept(cache: DatabaseCache) -> None:
    directory = cache.path.parent
    directory.mkdir(parents=True)
    unrelated_build = directory / "build-output"
    unrelated_build.mkdir()
    old_time = time.time() - 2 * CacheDirectory.STALE_WORKING_SECONDS
    os.utime(unrelated_build, (old_time, old_time))
    backup = directory / f"{cache.path.name}.bak"
    _ = backup.write_bytes(b"backup")
    assert cache.describe().obsolete_paths == ()
    path = cache.ensure()
    assert cache.clear() == [path]
    assert unrelated_build.is_dir()
    assert backup.is_file()


def test_refresh_downloads_the_same_files_again(cache: DatabaseCache) -> None:
    cache.ensure_lots(["113247"])
    before = imported_names(cache)
    cache.refresh()
    assert sorted(imported_names(cache)) == sorted(before)
    assert cache_files(cache) == [cache.path.name]
    with AddressCodec(AddressDatabase.open_read_only(cache.path), cache) as codec:
        assert codec.locate("三芳町竹間沢123-4").is_exact


def test_failed_refresh_keeps_the_database(cache: DatabaseCache, mirror: Path) -> None:
    cache.ensure_lots(["113247"])
    content = cache.path.read_bytes()
    (mirror / "mt_town" / "mt_town_all.csv.zip").unlink()
    with pytest.raises(RegistryDownloadError):
        cache.refresh()
    assert cache.path.read_bytes() == content
    assert cache_files(cache) == [cache.path.name]


def test_cache_command(
    cache: DatabaseCache,
    mirror: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv(DatabaseCache.DIRECTORY_VARIABLE, str(cache.path.parent))
    monkeypatch.setenv(DatabaseCache.BASE_URL_VARIABLE, mirror.as_uri())
    cli = CommandLineInterface()
    assert cli.run(["cache"]) == 0
    assert "\nsize_mb\t0.0\n" in capsys.readouterr().out
    assert cli.run(["cache", "refresh"]) == 0
    assert cache.is_built
    _ = capsys.readouterr()
    assert cli.run(["cache", "clear"]) == 0
    assert capsys.readouterr().out == f"Removed {cache.path}\n"
    assert cli.run(["--database", str(cache.path), "cache"]) == 3
    _ = capsys.readouterr()
    arguments = ["cache", "prepare", "--municipality", "113247", "--no-areas"]
    assert cli.run(arguments) == 0
    assert cache.describe().lot_municipality_codes == ("113247",)


def offline(cache: DatabaseCache, mirror: Path) -> DatabaseCache:
    return DatabaseCache(
        cache.path.parent,
        RegistryDownloader(mirror.as_uri()),
        BoundaryDownloader(),
        is_download_allowed=False,
    )


def test_offline_cache_requires_a_prepared_database(cache: DatabaseCache, mirror: Path) -> None:
    with pytest.raises(DatasetNotImportedError, match="prepare"):
        _ = AddressCodec.open(cache=offline(cache, mirror))
    assert not cache.is_built


def test_offline_cache_answers_from_prepared_data(cache: DatabaseCache, mirror: Path) -> None:
    cache.prepare(municipality_codes=["131016"], is_area_included=False)
    for archive in mirror.rglob("*.zip"):
        archive.unlink()
    with AddressCodec.open(cache=offline(cache, mirror)) as codec:
        assert codec.locate("千代田区丸の内1-2-3").level is AddressLevel.RESIDENCE
        assert codec.locate("三芳町竹間沢123-4").level is AddressLevel.TOWN
    assert cache.describe().lot_municipality_codes == ("131016",)


def test_prepare_adds_every_municipality_of_a_prefecture(cache: DatabaseCache) -> None:
    cache.prepare(prefecture_codes=["11"], is_area_included=False)
    assert cache.describe().lot_municipality_codes == ("113247",)
    with pytest.raises(ValueError, match="01 to 47"):
        cache.prepare(prefecture_codes=["48"])


def test_expired_cache_is_refreshed_on_first_use(cache: DatabaseCache, mirror: Path) -> None:
    _ = cache.ensure()
    built_at = cache.describe().built_at
    time.sleep(0.01)
    aging = DatabaseCache(
        cache.path.parent,
        RegistryDownloader(mirror.as_uri()),
        BoundaryDownloader(),
        max_age=timedelta(milliseconds=1),
    )
    with AddressCodec.open(cache=aging):
        pass
    refreshed_at = cache.describe().built_at
    assert built_at is not None
    assert refreshed_at is not None
    assert refreshed_at > built_at
    with pytest.raises(ValueError, match="max_age"):
        _ = DatabaseCache.default(max_age=timedelta(0))


def test_open_rejects_a_path_and_a_cache(cache: DatabaseCache) -> None:
    with pytest.raises(ValueError, match="not both"):
        _ = AddressCodec.open(cache.path, cache=cache)


def test_caches_of_one_directory_add_files_once(cache: DatabaseCache, mirror: Path) -> None:
    _ = cache.ensure()
    caches = [
        DatabaseCache(cache.path.parent, RegistryDownloader(mirror.as_uri()), BoundaryDownloader())
        for _ in range(4)
    ]
    with ThreadPoolExecutor(max_workers=4) as executor:
        for future in [executor.submit(item.ensure_lots, ["113247"]) for item in caches]:
            future.result()
    names = imported_names(cache)
    assert len(names) == len(set(names))


def test_cache_logs_its_downloads(cache: DatabaseCache, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="address_codec_jp.database.cache"):
        cache.ensure_lots(["113247"])
    assert "Building the address database" in caplog.text
    assert "Adding 6 registry files" in caplog.text


def serve(mirror: Path, target: DistributedFile) -> None:
    archive_path = mirror / target.url_path
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.write(FIXTURE_DIRECTORY / FIXTURE_NAMES[target.dataset], "data.csv")


def test_unpublished_files_are_not_requested_again(cache: DatabaseCache, mirror: Path) -> None:
    cache.ensure_lots(["131016"])
    cache.ensure_lots(["113247"])
    parcel = DistributedFile(AbrDataset.PARCEL, "131016")
    serve(mirror, parcel)
    cache.ensure_lots(["131016"])
    assert parcel.file_name not in imported_names(cache)
    cache.refresh()
    cache.ensure_lots(["131016"])
    assert parcel.file_name in imported_names(cache)


def test_failed_refresh_of_an_expired_cache_keeps_it_in_use(
    cache: DatabaseCache, mirror: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _ = cache.ensure()
    content = cache.path.read_bytes()
    time.sleep(0.01)
    (mirror / "mt_town" / "mt_town_all.csv.zip").unlink()
    aging = DatabaseCache(
        cache.path.parent,
        RegistryDownloader(mirror.as_uri()),
        BoundaryDownloader(),
        max_age=timedelta(milliseconds=1),
    )
    with (
        caplog.at_level(logging.WARNING, logger="address_codec_jp.database.cache"),
        AddressCodec.open(cache=aging) as codec,
    ):
        assert str(codec.encode("千代田区丸の内1")) == "131016-0011001"
    assert "Could not refresh" in caplog.text
    assert cache.path.read_bytes() == content


def test_max_age_requires_downloads(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="is_download_allowed"):
        _ = DatabaseCache.default(
            directory=tmp_path, is_download_allowed=False, max_age=timedelta(days=1)
        )


def aging(cache: DatabaseCache, mirror: Path) -> DatabaseCache:
    return DatabaseCache(
        cache.path.parent,
        RegistryDownloader(mirror.as_uri()),
        BoundaryDownloader(),
        max_age=timedelta(milliseconds=1),
    )


def test_expired_cache_with_a_malformed_release_stays_in_use(
    cache: DatabaseCache, mirror: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _ = cache.ensure()
    content = cache.path.read_bytes()
    time.sleep(0.01)
    with zipfile.ZipFile(mirror / "mt_town" / "mt_town_all.csv.zip", "w") as archive:
        archive.writestr("data.csv", "not,a,town,master\n")
    with (
        caplog.at_level(logging.WARNING, logger="address_codec_jp.database.cache"),
        AddressCodec.open(cache=aging(cache, mirror)) as codec,
    ):
        assert str(codec.encode("千代田区丸の内1")) == "131016-0011001"
    assert "Could not refresh" in caplog.text
    assert cache.path.read_bytes() == content


def test_expired_cache_with_a_failing_build_stays_in_use(
    cache: DatabaseCache,
    mirror: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _ = cache.ensure()
    time.sleep(0.01)

    def fail(_loader: CacheLoader) -> None:
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(CacheLoader, "build", fail)
    with (
        caplog.at_level(logging.WARNING, logger="address_codec_jp.database.cache"),
        AddressCodec.open(cache=aging(cache, mirror)) as codec,
    ):
        assert str(codec.encode("千代田区丸の内1")) == "131016-0011001"
    assert "disk I/O error" in caplog.text


def other_process(cache: DatabaseCache, mirror: Path) -> DatabaseCache:
    return DatabaseCache(
        cache.path.parent, RegistryDownloader(mirror.as_uri()), BoundaryDownloader()
    )


def test_codec_on_a_refreshed_database_must_be_reopened(cache: DatabaseCache, mirror: Path) -> None:
    with AddressCodec(cache.open_database(), cache) as codec:
        other_process(cache, mirror).refresh()
        with pytest.raises(DatabaseReplacedError, match="open it again"):
            _ = codec.locate("三芳町竹間沢123-4")
    assert cache.describe().lot_municipality_codes == ()
    with AddressCodec(cache.open_database(), cache) as codec:
        assert codec.locate("三芳町竹間沢123-4").is_exact


def test_codec_on_a_cleared_database_does_not_rebuild_it(
    cache: DatabaseCache, mirror: Path
) -> None:
    with AddressCodec(cache.open_database(), cache) as codec:
        _ = other_process(cache, mirror).clear()
        with pytest.raises(DatasetNotImportedError):
            _ = codec.locate("三芳町竹間沢123-4")
        assert not cache.is_built


def test_offline_codec_keeps_reading_a_replaced_database(
    cache: DatabaseCache, mirror: Path
) -> None:
    cache.prepare(municipality_codes=["113247"], is_area_included=False)
    service = offline(cache, mirror)
    with AddressCodec(service.open_database(), service) as codec:
        _ = other_process(cache, mirror).clear()
        assert codec.locate("三芳町竹間沢123-4").is_exact


def test_closed_codecs_do_not_block_additions(cache: DatabaseCache, mirror: Path) -> None:
    with AddressCodec(cache.open_database(), cache):
        pass
    other_process(cache, mirror).refresh()
    cache.ensure_lots(["113247"])
    assert cache.describe().lot_municipality_codes == ("113247",)


def test_ledger_is_read_again_after_another_process_rebuilds(
    cache: DatabaseCache, mirror: Path
) -> None:
    cache.ensure_lots(["113247"])
    other = other_process(cache, mirror)
    _ = other.clear()
    _ = other.ensure()
    assert cache.describe().lot_municipality_codes == ()
    cache.ensure_lots(["113247"])
    assert cache.describe().lot_municipality_codes == ("113247",)
