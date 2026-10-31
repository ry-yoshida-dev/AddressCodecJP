import io
import json
import sqlite3
from pathlib import Path
from typing import cast

import pytest

from address_codec_jp import AddressCodec, AddressMatch, DatasetNotImportedError
from address_codec_jp.frontends.cli import (
    CommandArguments,
    CommandLineInterface,
    ExitStatus,
    MaintenanceCommand,
    ParserFactory,
)
from address_codec_jp.frontends.query import QueryOperation

FIXTURE: Path = Path(__file__).parent / "fixtures" / "mt_town_sample.csv"
POSITION_SOURCES: list[str] = sorted(
    str(path) for path in (FIXTURE.parent / "positions").glob("*.csv")
)
CENSUS_BOUNDARY: Path = FIXTURE.parent / "areas" / "census_boundary_131016.zip"


@pytest.fixture
def database(tmp_path: Path) -> Path:
    """Database imported from the sample town master through the CLI."""
    database_path = tmp_path / "towns.sqlite3"
    assert (
        CommandLineInterface().run(["--database", str(database_path), "import", str(FIXTURE)]) == 0
    )
    return database_path


def test_commands_parse_to_their_enums() -> None:
    parser = ParserFactory().build()
    for operation in QueryOperation:
        namespace = parser.parse_args([operation.value], namespace=CommandArguments())
        assert namespace.command is operation
    maintenance_arguments: dict[MaintenanceCommand, list[str]] = {
        MaintenanceCommand.IMPORT: ["registry.csv"],
        MaintenanceCommand.IMPORT_AREA: ["boundary.zip", "--lg-code", "131016"],
        MaintenanceCommand.DOWNLOAD: ["downloads"],
        MaintenanceCommand.INFO: [],
        MaintenanceCommand.CACHE: [],
    }
    assert set(maintenance_arguments) == set(MaintenanceCommand)
    for command, arguments in maintenance_arguments.items():
        namespace = parser.parse_args([command.value, *arguments], namespace=CommandArguments())
        assert namespace.command is command


def test_encode_and_decode(database: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cli = CommandLineInterface()
    assert cli.run(["--database", str(database), "encode", "千代田区丸の内1-2-3"]) == 0
    assert (
        cli.run(["--database", str(database), "decode", "131016-0011001-2-3", "--numeral", "kanji"])
        == 0
    )
    assert capsys.readouterr().out.splitlines()[-2:] == [
        "千代田区丸の内1-2-3\t131016-0011001-2-3",
        "131016-0011001-2-3\t東京都千代田区丸の内一丁目二番三号",
    ]


@pytest.mark.parametrize(
    "arguments",
    [
        ["decode", "131016-9999999"],
        ["decode", "abc"],
        ["decode", "131016-0011000-1-2"],
        ["encode", "府中市"],
    ],
)
def test_errors_are_reported_without_traceback(
    database: Path, capsys: pytest.CaptureFixture[str], arguments: list[str]
) -> None:
    assert CommandLineInterface().run(["--database", str(database), *arguments]) == 1
    captured = capsys.readouterr()
    assert captured.out.startswith(f"{arguments[1]}\tERROR\t")
    assert "Traceback" not in captured.err


def test_missing_database_is_reported(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert (
        CommandLineInterface().run(
            ["--database", str(tmp_path / "none.sqlite3"), "encode", "東京都"]
        )
        == ExitStatus.FATAL_ERROR
    )
    assert "not found" in capsys.readouterr().err
    assert not (tmp_path / "none.sqlite3").exists()


def test_import_of_missing_file_is_reported(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    arguments = [
        "--database",
        str(tmp_path / "towns.sqlite3"),
        "import",
        str(tmp_path / "none.csv"),
    ]
    assert CommandLineInterface().run(arguments) == ExitStatus.FATAL_ERROR
    assert "not found" in capsys.readouterr().err


def test_import_and_locate(database: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cli = CommandLineInterface()
    assert cli.run(["--database", str(database), "import", *POSITION_SOURCES]) == 0
    assert cli.run(["--database", str(database), "locate", "千代田区丸の内1-2-9"]) == 0
    assert capsys.readouterr().out.splitlines()[-1] == "\t".join(
        [
            "千代田区丸の内1-2-9",
            "131016-0011001-2-9",
            "131016-0011001-2",
            "BLOCK",
            "35.682000000",
            "139.765000000",
            "EPSG:6668",
        ]
    )


def test_locate_without_positions_is_reported(
    database: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert CommandLineInterface().run(["--database", str(database), "locate", "東京都"]) == 1
    assert "No positions" in capsys.readouterr().out


def test_inputs_are_read_from_standard_input(
    database: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("千代田区丸の内1-2-3\n台東区浅草橋\n"))
    assert CommandLineInterface().run(["--database", str(database), "encode"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "千代田区丸の内1-2-3\t131016-0011001-2-3",
        "台東区浅草橋\t131067-0004000",
    ]


def test_blank_input_lines_keep_jsonl_output_aligned(
    database: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("千代田区丸の内1-2-3\n\n台東区浅草橋\n"))
    arguments = ["--database", str(database), "encode", "--output", "jsonl"]
    assert CommandLineInterface().run(arguments) == 1
    records: list[dict[str, object]] = [
        json.loads(line) for line in capsys.readouterr().out.splitlines()
    ]
    assert [record.get("code") for record in records] == [
        "131016-0011001-2-3",
        None,
        "131067-0004000",
    ]
    assert records[1]["error_type"] == "ValueError"


def test_jsonl_output_keeps_errors_in_line(
    database: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    arguments = ["--database", str(database), "encode", "--output", "jsonl"]
    assert CommandLineInterface().run([*arguments, "千代田区丸の内1-2-3 ビル", "府中市"]) == 1
    records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert records[0] == {
        "input": "千代田区丸の内1-2-3 ビル",
        "code": "131016-0011001-2-3",
        "level": "RESIDENCE",
        "remainder": "ビル",
        "town_name_tier": "EXACT",
    }
    assert records[1]["input"] == "府中市"
    assert "ambiguous" in records[1]["error"]
    assert records[1]["error_type"] == "AmbiguousAddressError"
    assert records[1]["candidates"] == ["132063", "342084"]


def test_decode_writes_kana_and_postal_code(
    database: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    arguments = ["--database", str(database), "decode", "131016-0011001-2-3"]
    assert CommandLineInterface().run([*arguments, "--kana", "--postal-code"]) == 0
    assert (
        capsys.readouterr().out.strip()
        == "131016-0011001-2-3\t〒100-0005 トウキョウトチヨダクマルノウチ1チョウメ2バン3ゴウ"
    )


def test_encode_verifies_lots(database: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cli = CommandLineInterface()
    assert cli.run(["--database", str(database), "import", *POSITION_SOURCES]) == 0
    arguments = ["--database", str(database), "encode", "--verify-lot"]
    assert cli.run([*arguments, "千代田区丸の内1-2-3"]) == 0
    assert cli.run([*arguments, "千代田区丸の内1-2-9"]) == 1
    assert "not registered" in capsys.readouterr().out


def test_nearest(database: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cli = CommandLineInterface()
    assert cli.run(["--database", str(database), "import", *POSITION_SOURCES]) == 0
    _ = capsys.readouterr()
    arguments = ["--database", str(database), "nearest", "35.682456,139.765123", "north"]
    assert cli.run(arguments) == 1
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == (
        "\t".join(
            [
                "35.682456,139.765123",
                "131016-0011001-2-3",
                "東京都千代田区丸の内1丁目2番3号",
                "RESIDENCE",
                "35.682456000",
                "139.765123000",
                "0.0",
                "EPSG:6668",
            ]
        )
    )
    assert lines[1].startswith("north\tERROR\tValueError\t")
    assert "latitude,longitude" in lines[1]


def test_invalid_enum_option_is_rejected(
    database: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as raised:
        _ = CommandLineInterface().run(["--database", str(database), "locate", "--crs", "x", "a"])
    assert raised.value.code == 2
    assert "{tokyo,jgd2000,jgd2011,wgs84}" in capsys.readouterr().err


@pytest.fixture
def located_database(database: Path) -> Path:
    """Database with the sample positions and the census boundaries of Chiyoda."""
    cli = CommandLineInterface()
    assert cli.run(["--database", str(database), "import", *POSITION_SOURCES]) == 0
    arguments = ["--database", str(database), "import-area", "--lg-code", "131016"]
    assert cli.run([*arguments, str(CENSUS_BOUNDARY)]) == 0
    return database


def read_records(output: str) -> list[dict[str, object]]:
    return [json.loads(line) for line in output.splitlines()]


def test_tsv_rows_start_with_their_input(
    database: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    arguments = ["--database", str(database), "children", "131016-0011001", "130001", "abc"]
    assert CommandLineInterface().run(arguments) == ExitStatus.INPUT_FAILURE
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "131016-0011001"
    assert lines[1] == "130001\t131016\t東京都千代田区\tMUNICIPALITY"
    assert all(line.startswith("130001\t") for line in lines[1:-1])
    assert lines[-1].startswith("abc\tERROR\tValueError\t")


def test_postal_and_name_list_areas_or_report_nothing_found(
    database: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cli = CommandLineInterface()
    arguments = ["--database", str(database)]
    assert cli.run([*arguments, "postal", "100-0005", "999-9999"]) == ExitStatus.INPUT_FAILURE
    assert cli.run([*arguments, "name", "丸の内", "存在しない"]) == ExitStatus.INPUT_FAILURE
    assert capsys.readouterr().out.splitlines() == [
        "100-0005\t131016-0011001\t東京都千代田区丸の内1丁目",
        "100-0005\t131016-0011002\t東京都千代田区丸の内2丁目",
        "100-0005\t131016-0011003\t東京都千代田区丸の内3丁目",
        "999-9999\tERROR\tAddressNotFoundError\tNo town is registered with '999-9999'.",
        "丸の内\t131016-0011000\t東京都千代田区丸の内\tTOWN",
        "存在しない\tERROR\tAddressNotFoundError\tNo area is named '存在しない'.",
    ]
    assert cli.run([*arguments, "name", "丸の内", "--output", "jsonl"]) == ExitStatus.SUCCESS
    assert json.loads(capsys.readouterr().out) == {
        "input": "丸の内",
        "name": "丸の内",
        "areas": [{"code": "131016-0011000", "address": "東京都千代田区丸の内", "level": "TOWN"}],
    }


def test_tsv_values_keep_the_columns(database: Path, capsys: pytest.CaptureFixture[str]) -> None:
    arguments = ["--database", str(database), "encode", "千代田\t丸の内\n1-2-3"]
    _ = CommandLineInterface().run(arguments)
    output = capsys.readouterr().out
    assert output.splitlines()[0].split("\t")[0] == "千代田 丸の内 1-2-3"
    assert len(output.splitlines()) == 1


def test_library_errors_do_not_stop_standard_input(
    database: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    original_match = AddressCodec.match
    failures: list[Exception] = [
        DatasetNotImportedError("Not imported."),
        sqlite3.OperationalError("database is locked"),
        OverflowError("Python int too large to convert to SQLite INTEGER"),
    ]

    def match(codec: AddressCodec, address: str, *, is_lot_verified: bool = False) -> AddressMatch:
        if failures:
            raise failures.pop(0)
        return original_match(codec, address, is_lot_verified=is_lot_verified)

    monkeypatch.setattr(AddressCodec, "match", match)
    monkeypatch.setattr("sys.stdin", io.StringIO("東京都\n東京都\n東京都\n台東区浅草橋\n"))
    arguments = ["--database", str(database), "encode", "--output", "jsonl"]
    assert CommandLineInterface().run(arguments) == ExitStatus.INPUT_FAILURE
    records = read_records(capsys.readouterr().out)
    assert [record.get("error_type") for record in records] == [
        "DatasetNotImportedError",
        "OperationalError",
        "OverflowError",
        None,
    ]
    assert records[3]["code"] == "131067-0004000"


def test_huge_lot_numbers_are_input_errors(
    database: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    huge = "千代田区丸の内1-" + "9" * 30
    arguments = ["--database", str(database), "encode", "--verify-lot", huge, "東京都"]
    assert CommandLineInterface().run(arguments) == ExitStatus.INPUT_FAILURE
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith(f"{huge}\tERROR\t")
    assert lines[1] == "東京都\t130001"


def test_decode_jsonl_names_the_code(database: Path, capsys: pytest.CaptureFixture[str]) -> None:
    arguments = ["--database", str(database), "decode", "131016-0011001", "--output", "jsonl"]
    assert CommandLineInterface().run(arguments) == ExitStatus.SUCCESS
    assert read_records(capsys.readouterr().out) == [
        {
            "input": "131016-0011001",
            "code": "131016-0011001",
            "address": "東京都千代田区丸の内1丁目",
        }
    ]


def test_locate_code(located_database: Path, capsys: pytest.CaptureFixture[str]) -> None:
    arguments = ["--database", str(located_database), "locate-code", "131016-0011001-2-3"]
    assert CommandLineInterface().run([*arguments, "--output", "jsonl"]) == ExitStatus.SUCCESS
    record = read_records(capsys.readouterr().out)[0]
    assert (record["located_code"], record["level"]) == ("131016-0011001-2-3", "RESIDENCE")


def test_area_geometry_can_be_omitted(
    located_database: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cli = CommandLineInterface()
    database_arguments = ["--database", str(located_database)]
    assert cli.run([*database_arguments, "area", "千代田区丸の内1丁目", "--output", "jsonl"]) == 0
    assert cli.run([*database_arguments, "area-code", "131016-0011001", "--no-geometry"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert "geometry" in json.loads(lines[0])
    assert lines[1] == "\t".join(
        ["131016-0011001", "131016-0011001", "131016-0011001", "TOWN", "census_boundary"]
    )


def area_fields(record: dict[str, object]) -> list[dict[str, object]]:
    areas = record["areas"]
    assert isinstance(areas, list)
    return [cast(dict[str, object], area) for area in cast(list[object], areas)]


def test_areas_at_adds_geometry_on_request(
    located_database: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cli = CommandLineInterface()
    arguments = ["--database", str(located_database), "areas-at", "35.6822,139.7660"]
    assert cli.run([*arguments, "--output", "jsonl"]) == ExitStatus.SUCCESS
    assert cli.run([*arguments, "--output", "jsonl", "--geometry"]) == ExitStatus.SUCCESS
    without, with_geometry = read_records(capsys.readouterr().out)
    assert ["geometry" in area for area in area_fields(without)] == [False]
    assert ["geometry" in area for area in area_fields(with_geometry)] == [True]
