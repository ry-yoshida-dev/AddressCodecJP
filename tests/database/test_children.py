import json
from pathlib import Path

import pytest

from address_codec_jp import AddressCode, AddressCodec, AddressNotFoundError
from address_codec_jp.frontends.cli import CommandLineInterface
from tests.fixture_paths import TOWN_MASTER


@pytest.mark.parametrize(
    ("code", "children"),
    [
        ("130001", ["131016", "131032", "131067", "132063"]),
        ("140007", ["141046"]),
        ("131016", ["131016-0002000", "131016-0011000", "131016-0054000"]),
        ("131016-0011000", ["131016-0011001", "131016-0011002", "131016-0011003"]),
        ("113247-0001000", ["113247-0001001"]),
        ("131016-0011001", []),
        ("113247-0001001", []),
    ],
)
def test_children_are_listed(codec: AddressCodec, code: str, children: list[str]) -> None:
    assert [str(child.code) for child in codec.list_children(code)] == children


def test_children_without_a_registered_oaza_are_listed_under_the_municipality(
    codec: AddressCodec,
) -> None:
    assert [str(child.code) for child in codec.list_children("014052")] == [
        "014052-0001001",
        "014052-0001002",
    ]
    assert [str(child.code) for child in codec.list_children("155861")] == ["155861-0000162"]


@pytest.mark.parametrize("code", ["130001", "131016", "131067", "131016-0011000", "172049"])
def test_every_child_has_the_code_as_parent(codec: AddressCodec, code: str) -> None:
    parent = AddressCode.parse(code)
    for child in codec.list_children(parent):
        assert child.code.parent == parent


@pytest.mark.parametrize("code", ["131016-9999000", "139998", "450006"])
def test_unregistered_area_is_rejected(codec: AddressCodec, code: str) -> None:
    with pytest.raises(AddressNotFoundError):
        _ = codec.list_children(code)


def test_lot_numbers_are_rejected(codec: AddressCodec) -> None:
    with pytest.raises(ValueError, match="lot numbers"):
        _ = codec.list_children("131016-0011001-2")


def test_children_command(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    database = str(tmp_path / "towns.sqlite3")
    cli = CommandLineInterface()
    assert cli.run(["--database", database, "import", str(TOWN_MASTER)]) == 0
    assert (
        cli.run(["--database", database, "children", "131016-0011000", "--numeral", "kanji"]) == 0
    )
    assert capsys.readouterr().out.splitlines()[-3:] == [
        "131016-0011000\t131016-0011001\t東京都千代田区丸の内一丁目\tTOWN",
        "131016-0011000\t131016-0011002\t東京都千代田区丸の内二丁目\tTOWN",
        "131016-0011000\t131016-0011003\t東京都千代田区丸の内三丁目\tTOWN",
    ]
    assert cli.run(["--database", database, "children", "--output", "jsonl", "130001"]) == 0
    records: list[dict[str, object]] = [
        json.loads(line) for line in capsys.readouterr().out.splitlines()
    ]
    assert records[0]["children"] == [
        {"code": "131016", "address": "東京都千代田区", "level": "MUNICIPALITY"},
        {"code": "131032", "address": "東京都港区", "level": "MUNICIPALITY"},
        {"code": "131067", "address": "東京都台東区", "level": "MUNICIPALITY"},
        {"code": "132063", "address": "東京都府中市", "level": "MUNICIPALITY"},
    ]
