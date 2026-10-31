import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from address_codec_jp import AbrDataset, AddressCodec, DatasetImport, RegistryImporter
from address_codec_jp.frontends.cli import CommandLineInterface
from tests.fixture_paths import FIXTURE_DIRECTORY

TOWN_MASTER: Path = FIXTURE_DIRECTORY / "mt_town_sample.csv"
TOWN_POSITIONS: Path = FIXTURE_DIRECTORY / "positions" / "mt_town_pos_sample.csv"


def test_imports_are_logged_with_digests(tmp_path: Path) -> None:
    database = tmp_path / "towns.sqlite3"
    started_at = datetime.now(UTC)
    with RegistryImporter.open(database) as importer:
        town_summary = importer.import_file(TOWN_MASTER)
        position_summary = importer.import_file(TOWN_POSITIONS)
    with AddressCodec.open(database) as codec:
        imports = codec.list_imports()
    assert [(item.dataset, item.source_name, item.row_count) for item in imports] == [
        (AbrDataset.TOWN, "mt_town_sample.csv", town_summary.stored_count),
        (AbrDataset.TOWN_POSITION, "mt_town_pos_sample.csv", position_summary.stored_count),
    ]
    assert imports[0].source_sha256 == hashlib.sha256(TOWN_MASTER.read_bytes()).hexdigest()
    assert all(item.imported_at >= started_at for item in imports)


def test_failed_import_is_not_logged(importer: RegistryImporter, tmp_path: Path) -> None:
    broken = tmp_path / "broken.csv"
    _ = broken.write_text("lg_code,rep_lon,rep_lat,rep_srid\n130001,139.0,35.0,EPSG:1\n")
    with pytest.raises(ValueError, match="Row 2"):
        _ = importer.import_file(broken)
    assert [item.dataset for item in AddressCodec(importer.database).list_imports()] == [
        AbrDataset.TOWN
    ]


def test_dataset_import_requires_time_zone() -> None:
    with pytest.raises(ValueError, match="time zone"):
        _ = DatasetImport(
            dataset=AbrDataset.TOWN,
            source_name="mt_town_all.csv",
            source_sha256="0" * 64,
            imported_at=datetime(2026, 10, 1),
            row_count=1,
        )


def test_info_command_lists_imports(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    database = str(tmp_path / "towns.sqlite3")
    assert CommandLineInterface().run(["--database", database, "import", str(TOWN_MASTER)]) == 0
    _ = capsys.readouterr()
    assert CommandLineInterface().run(["--database", database, "info"]) == 0
    columns = capsys.readouterr().out.strip().split("\t")
    assert columns[1:4] == ["mt_town", "58", "mt_town_sample.csv"]
    assert len(columns[4]) == 64
