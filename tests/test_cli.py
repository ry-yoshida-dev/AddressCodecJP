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
        cli.run(["--database", str(database), "decode", "131016-0001001-2-3", "--numeral", "kanji"])
        == 0
    )
    assert capsys.readouterr().out.splitlines()[-2:] == [
        "131016-0001001-2-3",
        "東京都千代田区丸の内一丁目二番三号",
    ]


@pytest.mark.parametrize(
    "arguments",
    [
        ["decode", "131016-9999999"],
        ["decode", "abc"],
        ["decode", "131016-0001000-1-2"],
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


def test_import_positions_and_locate(database: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cli = CommandLineInterface()
    sources = sorted(str(path) for path in (FIXTURE.parent / "positions").glob("*.csv"))
    assert cli.run(["--database", str(database), "import-positions", *sources]) == 0
    assert cli.run(["--database", str(database), "locate", "千代田区丸の内1-2-9"]) == 0
    assert capsys.readouterr().out.splitlines()[-1] == "\t".join(
        [
            "131016-0001001-2-9",
            "131016-0001001-2",
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
