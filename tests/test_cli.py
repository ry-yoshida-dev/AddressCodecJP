import io
import json
from pathlib import Path

import pytest

from address_codec_jp.cli import CommandLineInterface

FIXTURE: Path = Path(__file__).parent / "fixtures" / "mt_town_sample.csv"


@pytest.fixture
def database(tmp_path: Path) -> Path:
    """Database imported from the sample town master through the CLI."""
    database_path = tmp_path / "towns.sqlite3"
    assert (
        CommandLineInterface().run(["--database", str(database_path), "import", str(FIXTURE)]) == 0
    )
    return database_path


def test_encode_and_decode(database: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cli = CommandLineInterface()
    assert cli.run(["--database", str(database), "encode", "千代田区丸の内1-2-3"]) == 0
    assert (
        cli.run(["--database", str(database), "decode", "131016-0011001-2-3", "--numeral", "kanji"])
        == 0
    )
    assert capsys.readouterr().out.splitlines()[-2:] == [
        "131016-0011001-2-3",
        "東京都千代田区丸の内一丁目二番三号",
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
    error_output = capsys.readouterr().err
    assert "ERROR" in error_output
    assert "Traceback" not in error_output


def test_missing_database_is_reported(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert (
        CommandLineInterface().run(
            ["--database", str(tmp_path / "none.sqlite3"), "encode", "東京都"]
        )
        == 1
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
    assert CommandLineInterface().run(arguments) == 1
    assert "not found" in capsys.readouterr().err


def test_import_and_locate(database: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cli = CommandLineInterface()
    sources = sorted(str(path) for path in (FIXTURE.parent / "positions").glob("*.csv"))
    assert cli.run(["--database", str(database), "import", *sources]) == 0
    assert cli.run(["--database", str(database), "locate", "千代田区丸の内1-2-9"]) == 0
    assert capsys.readouterr().out.splitlines()[-1] == "\t".join(
        [
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
    assert "No positions" in capsys.readouterr().err


def test_inputs_are_read_from_standard_input(
    database: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("千代田区丸の内1-2-3\n台東区浅草橋\n"))
    assert CommandLineInterface().run(["--database", str(database), "encode"]) == 0
    assert capsys.readouterr().out.splitlines() == ["131016-0011001-2-3", "131067-0004000"]


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
        == "〒100-0005 トウキョウトチヨダクマルノウチ1チョウメ2バン3ゴウ"
    )


def test_encode_verifies_lots(database: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cli = CommandLineInterface()
    sources = sorted(str(path) for path in (FIXTURE.parent / "positions").glob("*.csv"))
    assert cli.run(["--database", str(database), "import", *sources]) == 0
    arguments = ["--database", str(database), "encode", "--verify-lot"]
    assert cli.run([*arguments, "千代田区丸の内1-2-3"]) == 0
    assert cli.run([*arguments, "千代田区丸の内1-2-9"]) == 1
    assert "not registered" in capsys.readouterr().err


def test_nearest(database: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cli = CommandLineInterface()
    sources = sorted(str(path) for path in (FIXTURE.parent / "positions").glob("*.csv"))
    assert cli.run(["--database", str(database), "import", *sources]) == 0
    _ = capsys.readouterr()
    arguments = ["--database", str(database), "nearest", "35.682456,139.765123", "north"]
    assert cli.run(arguments) == 1
    captured = capsys.readouterr()
    assert captured.out.splitlines() == [
        "\t".join(
            [
                "131016-0011001-2-3",
                "東京都千代田区丸の内1丁目2番3号",
                "RESIDENCE",
                "35.682456000",
                "139.765123000",
                "0.0",
                "EPSG:6668",
            ]
        )
    ]
    assert "latitude,longitude" in captured.err


def test_invalid_enum_option_is_rejected(
    database: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as raised:
        _ = CommandLineInterface().run(["--database", str(database), "locate", "--crs", "x", "a"])
    assert raised.value.code == 2
    assert "{tokyo,jgd2000,jgd2011,wgs84}" in capsys.readouterr().err
