import zipfile
from pathlib import Path

import pytest
from geo_coordinate import GeoCoordinate

from address_codec_jp import (
    AbrDataset,
    AddressCodec,
    AddressDatabase,
    AddressLevel,
    DatabaseCache,
    DistributedFile,
    DistributionScope,
    RegistryDownloader,
    RegistryDownloadError,
)
from address_codec_jp.cli import CommandLineInterface

FIXTURE_DIRECTORY: Path = Path(__file__).parent / "fixtures"
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
    return DatabaseCache(tmp_path / "cache", RegistryDownloader(mirror.as_uri()))


def test_ensure_builds_the_town_level_database(cache: DatabaseCache) -> None:
    assert not cache.is_built
    path = cache.ensure()
    assert path == cache.path
    assert path.name == f"towns-v{AddressDatabase.SCHEMA_VERSION}.sqlite3"
    assert list(path.parent.iterdir()) == [path]
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
    assert list(cache.path.parent.iterdir()) == []


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
    assert captured.out.splitlines() == ["131016-0011001-2-3"]
    assert captured.err == ""


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
    DatabaseCache(cache.path.parent, RegistryDownloader(mirror.as_uri())).ensure_lots(["131016"])
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
