import email.message
import io
import shutil
import time
import urllib.request
import urllib.response
import zipfile
from pathlib import Path
from typing import BinaryIO

import pytest

from address_codec_jp import (
    AbrDataset,
    AddressCodec,
    AddressLevel,
    DistributedFile,
    RegistryDownloader,
    RegistryDownloadError,
)
from address_codec_jp.datasets.download import FileFetcher
from address_codec_jp.frontends.cli import CommandLineInterface

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


@pytest.fixture
def mirror(tmp_path: Path) -> Path:
    """Build a local mirror of the download site serving the fixtures for Tokyo and Miyoshi."""
    root = tmp_path / "mirror"
    for target in RegistryDownloader().plan(["13"], ["113247"]):
        archive_path = root / target.url_path
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.write(FIXTURE_DIRECTORY / FIXTURE_NAMES[target.dataset], "data.csv")
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
    ("dataset", "area_code"),
    [
        (AbrDataset.TOWN, "13"),
        (AbrDataset.TOWN_POSITION, None),
        (AbrDataset.TOWN_POSITION, "48"),
        (AbrDataset.TOWN_POSITION, "131016"),
        (AbrDataset.PARCEL, "130001"),
        (AbrDataset.PARCEL, "131017"),
    ],
)
def test_distributed_file_rejects_area_codes_of_another_scope(
    dataset: AbrDataset, area_code: str | None
) -> None:
    with pytest.raises(ValueError, match=r"area code|prefecture code|check digit|six digits"):
        _ = DistributedFile(dataset, area_code)


def test_download_writes_the_file(mirror: Path, tmp_path: Path) -> None:
    downloader = RegistryDownloader(mirror.as_uri())
    path = downloader.download(DistributedFile(AbrDataset.TOWN), tmp_path / "data")
    assert path == tmp_path / "data" / "mt_town_all.csv.zip"
    assert path.read_bytes() == (mirror / "mt_town" / "mt_town_all.csv.zip").read_bytes()


def test_missing_file_raises_and_leaves_nothing(mirror: Path, tmp_path: Path) -> None:
    downloader = RegistryDownloader(mirror.as_uri())
    directory = tmp_path / "data"
    with pytest.raises(RegistryDownloadError, match="mt_town_pos_pref01"):
        _ = downloader.download(DistributedFile(AbrDataset.TOWN_POSITION, "01"), directory)
    assert list(directory.iterdir()) == []


def test_existing_file_can_be_kept(mirror: Path, tmp_path: Path) -> None:
    directory = tmp_path / "data"
    directory.mkdir()
    existing = directory / "mt_town_all.csv.zip"
    _ = existing.write_bytes(b"kept")
    downloader = RegistryDownloader(mirror.as_uri())
    target = DistributedFile(AbrDataset.TOWN)
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


def test_truncated_download_raises_and_leaves_nothing(
    mirror: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def copy_half(source: BinaryIO, destination: BinaryIO) -> None:
        content = source.read()
        _ = destination.write(content[: len(content) // 2])

    monkeypatch.setattr(shutil, "copyfileobj", copy_half)
    directory = tmp_path / "data"
    downloader = RegistryDownloader(mirror.as_uri())
    with pytest.raises(RegistryDownloadError, match="Received"):
        _ = downloader.download(DistributedFile(AbrDataset.TOWN), directory)
    assert list(directory.iterdir()) == []


def test_failed_write_raises_and_leaves_nothing(
    mirror: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_to_write(source: BinaryIO, destination: BinaryIO) -> None:
        _ = destination.write(source.read(10))
        raise OSError("No space left on device")

    monkeypatch.setattr(shutil, "copyfileobj", fail_to_write)
    directory = tmp_path / "data"
    downloader = RegistryDownloader(mirror.as_uri())
    with pytest.raises(RegistryDownloadError, match="No space left"):
        _ = downloader.download(DistributedFile(AbrDataset.TOWN), directory)
    assert list(directory.iterdir()) == []


def test_remote_requests_are_spaced_and_identified(monkeypatch: pytest.MonkeyPatch) -> None:
    user_agents: list[str | None] = []
    timeouts: list[float] = []
    waits: list[float] = []

    def respond(request: urllib.request.Request, timeout: float) -> urllib.response.addinfourl:
        user_agents.append(request.get_header("User-agent"))
        timeouts.append(timeout)
        return urllib.response.addinfourl(
            io.BytesIO(b"{}"), email.message.Message(), request.full_url, 200
        )

    monkeypatch.setattr(urllib.request, "urlopen", respond)
    monkeypatch.setattr(time, "sleep", waits.append)
    fetcher = FileFetcher(timeout_seconds=30.0, request_interval_seconds=1.0)
    _ = fetcher.read("https://example.com/first")
    _ = fetcher.read("https://example.com/second")
    assert timeouts == [30.0, 30.0]
    assert len(waits) == 1
    assert 0.5 < waits[0] <= 1.0
    assert all(
        user_agent is not None and user_agent.startswith("address-codec-jp/")
        for user_agent in user_agents
    )


def test_local_files_are_read_without_waiting(
    mirror: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    waits: list[float] = []
    monkeypatch.setattr(time, "sleep", waits.append)
    downloader = RegistryDownloader(mirror.as_uri())
    for dataset in (AbrDataset.TOWN, AbrDataset.PREFECTURE_POSITION):
        _ = downloader.download(DistributedFile(dataset), tmp_path)
    assert waits == []


def test_negative_request_interval_is_rejected() -> None:
    with pytest.raises(ValueError, match="request_interval_seconds"):
        _ = FileFetcher(request_interval_seconds=-1.0)
