import zipfile
from pathlib import Path

import pytest

from address_codec_jp import (
    AbrDataset,
    AddressCodec,
    AddressDatabase,
    AddressLevel,
    DatabaseCache,
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
}


@pytest.fixture
def mirror(tmp_path: Path) -> Path:
    """Build a local mirror serving the town-level fixtures for every prefecture."""
    root = tmp_path / "mirror"
    for target in RegistryDownloader().plan([f"{number:02d}" for number in range(1, 48)]):
        if target.dataset not in FIXTURE_NAMES:
            continue
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
    assert datasets == set(FIXTURE_NAMES)


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


def test_default_uses_the_configured_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(DatabaseCache.DIRECTORY_VARIABLE, str(tmp_path))
    assert DatabaseCache.default().path.parent == tmp_path


def test_open_and_cli_default_to_the_cached_database(
    cache: DatabaseCache,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _ = cache.ensure()
    monkeypatch.setenv(DatabaseCache.DIRECTORY_VARIABLE, str(cache.path.parent))
    with AddressCodec.open() as codec:
        assert str(codec.encode("千代田区丸の内1-2-3")) == "131016-0011001-2-3"
    assert CommandLineInterface().run(["encode", "千代田区丸の内1-2-3"]) == 0
    captured = capsys.readouterr()
    assert captured.out.splitlines() == ["131016-0011001-2-3"]
    assert captured.err == ""
