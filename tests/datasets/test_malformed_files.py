import zipfile
from pathlib import Path

import pytest

from address_codec_jp import AbrDataset, BoundaryFormatError, RegistryFormatError
from address_codec_jp.datasets.address_base_registry import AbrCsvFile
from address_codec_jp.datasets.boundaries import ShapefileReader
from address_codec_jp.frontends.cli import CommandLineInterface, ExitStatus
from tests.fixture_paths import FIXTURE_DIRECTORY, TOWN_MASTER

CENSUS_BOUNDARY: Path = FIXTURE_DIRECTORY / "areas" / "census_boundary_131016.zip"


def write_broken_archive(path: Path, source: Path) -> Path:
    """Write ``source`` into a stored ZIP archive, then corrupt its data so the CRC fails."""
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.write(source, "data.csv")
    content = bytearray(path.read_bytes())
    data_start = content.index(source.read_bytes()[:64])
    content[data_start + len(source.read_bytes()) - 3] ^= 0x01
    _ = path.write_bytes(bytes(content))
    return path


def write_non_utf8_csv(path: Path) -> Path:
    text = TOWN_MASTER.read_text(encoding="utf-8-sig")
    _ = path.write_bytes(text.encode("cp932"))
    return path


def test_broken_registry_archive_is_a_format_error(tmp_path: Path) -> None:
    archive = write_broken_archive(tmp_path / "town.csv.zip", TOWN_MASTER)
    with pytest.raises(RegistryFormatError, match="broken ZIP"):
        _ = list(AbrCsvFile(archive).read_records(AbrDataset.TOWN))


def test_non_utf8_registry_csv_is_a_format_error(tmp_path: Path) -> None:
    plain = write_non_utf8_csv(tmp_path / "town.csv")
    with pytest.raises(RegistryFormatError, match="UTF-8"):
        _ = list(AbrCsvFile(plain).read_records(AbrDataset.TOWN))
    archive = tmp_path / "town.csv.zip"
    with zipfile.ZipFile(archive, "w") as writer:
        writer.write(plain, "data.csv")
    with pytest.raises(RegistryFormatError, match="UTF-8"):
        _ = list(AbrCsvFile(archive).read_records(AbrDataset.TOWN))


@pytest.mark.parametrize("is_archive_broken", [True, False])
def test_cli_import_of_a_malformed_file_exits_with_a_fatal_status(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], *, is_archive_broken: bool
) -> None:
    source = (
        write_broken_archive(tmp_path / "town.csv.zip", TOWN_MASTER)
        if is_archive_broken
        else write_non_utf8_csv(tmp_path / "town.csv")
    )
    arguments = ["--database", str(tmp_path / "towns.sqlite3"), "import", str(source)]
    assert CommandLineInterface().run(arguments) == ExitStatus.FATAL_ERROR
    error = capsys.readouterr().err
    assert error.startswith("ERROR: ")
    assert "Traceback" not in error


def test_shapefile_with_an_undecodable_attribute_table_is_a_format_error(tmp_path: Path) -> None:
    archive_path = tmp_path / "boundary.zip"
    with (
        zipfile.ZipFile(CENSUS_BOUNDARY) as source,
        zipfile.ZipFile(archive_path, "w") as target,
    ):
        for name in source.namelist():
            data = source.read(name)
            if name.lower().endswith(".dbf"):
                table = bytearray(data)
                table[32] = 0xFF
                data = bytes(table)
            target.writestr(name, data)
    with pytest.raises(BoundaryFormatError, match="malformed shapefile"):
        _ = ShapefileReader().read(archive_path)
