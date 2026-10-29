import zipfile
from pathlib import Path

import pytest

from address_codec_jp import (
    AddressCodec,
    AddressLevel,
    DownloadTarget,
    RegistryDownloader,
    RegistryDownloadError,
    RegistryFile,
)
from address_codec_jp.cli import CommandLineInterface

FIXTURE_DIRECTORY: Path = Path(__file__).parent / "fixtures"
FIXTURE_NAMES: dict[RegistryFile, str] = {
    RegistryFile.TOWN: "mt_town_sample.csv",
    RegistryFile.PREFECTURE_POSITION: "positions/mt_pref_pos_sample.csv",
    RegistryFile.MUNICIPALITY_POSITION: "positions/mt_city_pos_sample.csv",
    RegistryFile.TOWN_POSITION: "positions/mt_town_pos_sample.csv",
    RegistryFile.BLOCK: "positions/mt_rsdtdsp_blk_sample.csv",
    RegistryFile.BLOCK_POSITION: "positions/mt_rsdtdsp_blk_pos_sample.csv",
    RegistryFile.RESIDENCE: "positions/mt_rsdtdsp_rsdt_sample.csv",
    RegistryFile.RESIDENCE_POSITION: "positions/mt_rsdtdsp_rsdt_pos_sample.csv",
    RegistryFile.PARCEL: "positions/mt_parcel_sample.csv",
    RegistryFile.PARCEL_POSITION: "positions/mt_parcel_pos_sample.csv",
}


@pytest.fixture
def mirror(tmp_path: Path) -> Path:
    """Build a local mirror of the download site serving the fixtures for Tokyo and Miyoshi."""
    root = tmp_path / "mirror"
    for target in RegistryDownloader().plan(["13"], ["113247"]):
        archive_path = root / target.url_path
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.write(FIXTURE_DIRECTORY / FIXTURE_NAMES[target.registry_file], "data.csv")
    return root


def test_plan_lists_files_in_import_order() -> None:
    paths = [target.url_path for target in RegistryDownloader().plan(["13", "13"], ["312011"])]
    assert paths == [
        "mt_town/mt_town_all.csv.zip",
        "mt_pref_pos/mt_pref_pos_all.csv.zip",
        "mt_city_pos/mt_city_pos_all.csv.zip",
        "mt_town_pos/pref/mt_town_pos_pref13.csv.zip",
        "mt_rsdtdsp_blk/pref/mt_rsdtdsp_blk_pref13.csv.zip",
        "mt_rsdtdsp_blk_pos/pref/mt_rsdtdsp_blk_pos_pref13.csv.zip",
        "mt_rsdtdsp_rsdt/pref/mt_rsdtdsp_rsdt_pref13.csv.zip",
        "mt_rsdtdsp_rsdt_pos/pref/mt_rsdtdsp_rsdt_pos_pref13.csv.zip",
        "mt_parcel/city/mt_parcel_city312011.csv.zip",
        "mt_parcel_pos/city/mt_parcel_pos_city312011.csv.zip",
    ]


@pytest.mark.parametrize(
    ("registry_file", "area_code"),
    [
        (RegistryFile.TOWN, "13"),
        (RegistryFile.TOWN_POSITION, None),
        (RegistryFile.TOWN_POSITION, "48"),
        (RegistryFile.TOWN_POSITION, "131016"),
        (RegistryFile.PARCEL, "130001"),
        (RegistryFile.PARCEL, "131017"),
    ],
)
def test_target_rejects_area_codes_of_another_scope(
    registry_file: RegistryFile, area_code: str | None
) -> None:
    with pytest.raises(ValueError, match=r"area code|prefecture code|check digit"):
        _ = DownloadTarget(registry_file, area_code)


def test_download_writes_the_file(mirror: Path, tmp_path: Path) -> None:
    downloader = RegistryDownloader(mirror.as_uri())
    path = downloader.download(DownloadTarget(RegistryFile.TOWN), tmp_path / "data")
    assert path == tmp_path / "data" / "mt_town_all.csv.zip"
    assert path.read_bytes() == (mirror / "mt_town" / "mt_town_all.csv.zip").read_bytes()


def test_missing_file_raises_and_leaves_nothing(mirror: Path, tmp_path: Path) -> None:
    downloader = RegistryDownloader(mirror.as_uri())
    directory = tmp_path / "data"
    with pytest.raises(RegistryDownloadError, match="mt_town_pos_pref01"):
        _ = downloader.download(DownloadTarget(RegistryFile.TOWN_POSITION, "01"), directory)
    assert list(directory.iterdir()) == []


def test_existing_file_can_be_kept(mirror: Path, tmp_path: Path) -> None:
    directory = tmp_path / "data"
    directory.mkdir()
    existing = directory / "mt_town_all.csv.zip"
    _ = existing.write_bytes(b"kept")
    downloader = RegistryDownloader(mirror.as_uri())
    target = DownloadTarget(RegistryFile.TOWN)
    _ = downloader.download(target, directory, is_existing_kept=True)
    assert existing.read_bytes() == b"kept"
    _ = downloader.download(target, directory)
    assert existing.read_bytes() != b"kept"


def test_download_command_imports_the_files(
    mirror: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    database = tmp_path / "towns.sqlite3"
    arguments = [
        "--database",
        str(database),
        "download",
        str(tmp_path / "data"),
        "--prefecture",
        "13",
        "--municipality",
        "113247",
        "--import",
        "--base-url",
        mirror.as_uri(),
    ]
    assert CommandLineInterface().run(arguments) == 0
    assert capsys.readouterr().out.count("Downloaded") == 10
    with AddressCodec.open(database) as codec:
        assert codec.locate("千代田区丸の内1-2-3").level is AddressLevel.RESIDENCE
        assert len(codec.list_imports()) == 10
