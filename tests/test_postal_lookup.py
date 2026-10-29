import json
from pathlib import Path

import pytest

from address_codec_jp import AddressCodec
from address_codec_jp.cli import CommandLineInterface
from address_codec_jp.normalization import TextNormalizer

TOWN_MASTER: Path = Path(__file__).parent / "fixtures" / "mt_town_sample.csv"


@pytest.mark.parametrize("text", ["100-0005", "〒1000005", "１００－０００５", " 100 0005 "])
def test_postal_code_is_parsed(text: str) -> None:
    assert TextNormalizer().parse_postal_code(text) == "1000005"


@pytest.mark.parametrize("text", ["", "100-000", "1000005東京", "abc"])
def test_malformed_postal_code_is_rejected(text: str) -> None:
    with pytest.raises(ValueError, match="Invalid postal code"):
        _ = TextNormalizer().parse_postal_code(text)


def test_towns_are_listed_by_postal_code(codec: AddressCodec) -> None:
    addresses = codec.list_by_postal_code("〒100-0005")
    assert [str(address.code) for address in addresses] == [
        "131016-0001001",
        "131016-0001002",
        "131016-0001003",
    ]
    assert all(address.town is not None and address.town.is_registered for address in addresses)


def test_unknown_postal_code_lists_nothing(codec: AddressCodec) -> None:
    assert codec.list_by_postal_code("999-9999") == []


def test_postal_command(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    database = str(tmp_path / "towns.sqlite3")
    cli = CommandLineInterface()
    assert cli.run(["--database", database, "import", str(TOWN_MASTER)]) == 0
    assert cli.run(["--database", database, "postal", "100-0005", "--numeral", "kanji"]) == 0
    assert capsys.readouterr().out.splitlines()[-3:] == [
        "131016-0001001\t東京都千代田区丸の内一丁目",
        "131016-0001002\t東京都千代田区丸の内二丁目",
        "131016-0001003\t東京都千代田区丸の内三丁目",
    ]
    assert cli.run(["--database", database, "postal", "--output", "jsonl", "999-9999"]) == 1
    records: list[dict[str, object]] = [
        json.loads(line) for line in capsys.readouterr().out.splitlines()
    ]
    assert records[0]["error_type"] == "AddressNotFoundError"
    assert cli.run(["--database", database, "postal", "--output", "jsonl", "100-0005"]) == 0
    records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert records[0]["towns"] == [
        {"code": "131016-0001001", "address": "東京都千代田区丸の内1丁目"},
        {"code": "131016-0001002", "address": "東京都千代田区丸の内2丁目"},
        {"code": "131016-0001003", "address": "東京都千代田区丸の内3丁目"},
    ]
