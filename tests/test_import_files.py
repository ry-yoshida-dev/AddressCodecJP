from pathlib import Path

import pytest

from address_codec_jp import (
    AbrDataset,
    AddressCodec,
    AddressDatabase,
    RegistryFormatError,
    RegistryImporter,
)
from address_codec_jp.cli import CommandLineInterface

FIXTURE_DIRECTORY: Path = Path(__file__).parent / "fixtures"
TOWN_MASTER: Path = FIXTURE_DIRECTORY / "mt_town_sample.csv"
POSITION_FIXTURES: list[Path] = sorted((FIXTURE_DIRECTORY / "positions").glob("*.csv"))


def test_town_master_is_imported_first(tmp_path: Path) -> None:
    with RegistryImporter.open(tmp_path / "towns.sqlite3") as importer:
        summaries = importer.import_files([*POSITION_FIXTURES, TOWN_MASTER])
        codec = AddressCodec(importer.database)
        location = codec.locate("千代田区丸の内1-2-3")
    assert summaries[0].dataset is AbrDataset.TOWN
    assert summaries[0].source == TOWN_MASTER
    assert summaries[0].complemented_count > 0
    assert [summary.source for summary in summaries[1:]] == POSITION_FIXTURES
    assert location.is_exact


def test_unknown_file_is_reported_before_any_import(tmp_path: Path) -> None:
    unknown = tmp_path / "unknown.csv"
    _ = unknown.write_text("a,b\n1,2\n", encoding="utf-8")
    database = tmp_path / "towns.sqlite3"
    with RegistryImporter.open(database) as importer:
        with pytest.raises(RegistryFormatError, match="Not a dataset"):
            _ = importer.import_files([TOWN_MASTER, unknown])
        assert importer.database.towns.list_municipalities() == []
        assert importer.database.imports.list_all() == []


def test_transaction_rolls_back_on_error(importer: RegistryImporter) -> None:
    database = importer.database
    municipalities = database.towns.list_municipalities()

    def replace_and_fail() -> None:
        with database.transaction():
            _ = database.towns.replace_all([])
            _ = database.positions.remove_orphans()
            raise LookupError

    with pytest.raises(LookupError):
        replace_and_fail()
    assert database.towns.list_municipalities() == municipalities


def test_read_only_database_refuses_transactions(tmp_path: Path) -> None:
    path = tmp_path / "towns.sqlite3"
    with RegistryImporter.open(path) as importer:
        _ = importer.import_file(TOWN_MASTER)
    with (
        AddressDatabase.open_read_only(path) as database,
        pytest.raises(RuntimeError),
        database.transaction(),
    ):
        pass


def test_import_command_accepts_every_dataset(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    database = str(tmp_path / "towns.sqlite3")
    sources = [str(path) for path in [*POSITION_FIXTURES, TOWN_MASTER]]
    assert CommandLineInterface().run(["--database", database, "import", *sources]) == 0
    assert capsys.readouterr().out.splitlines()[0].startswith("Imported 42 rows of mt_town")


def test_database_option_defaults_to_towns_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    cli = CommandLineInterface()
    assert cli.run(["import", str(TOWN_MASTER)]) == 0
    assert (tmp_path / "towns.sqlite3").is_file()
    assert cli.run(["encode", "千代田区丸の内1-2-3"]) == 0
    assert capsys.readouterr().out.splitlines()[-1] == "131016-0001001-2-3"


def test_a_path_given_twice_is_imported_once(tmp_path: Path) -> None:
    with RegistryImporter.open(tmp_path / "towns.sqlite3") as importer:
        summaries = importer.import_files([TOWN_MASTER, TOWN_MASTER])
        assert [summary.source for summary in summaries] == [TOWN_MASTER]
        assert len(importer.database.imports.list_all()) == 1


def test_area_points_without_rows_cannot_be_identified(tmp_path: Path) -> None:
    empty = tmp_path / "mt_city_pos_all.csv"
    _ = empty.write_text("lg_code,rep_lon,rep_lat,rep_srid\n", encoding="utf-8")
    with (
        RegistryImporter.open(tmp_path / "towns.sqlite3") as importer,
        pytest.raises(RegistryFormatError, match="needs a data row"),
    ):
        _ = importer.import_file(empty)
