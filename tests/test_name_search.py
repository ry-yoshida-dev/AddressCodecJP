import json
from pathlib import Path

import pytest

from address_codec_jp import AddressCodec
from address_codec_jp.frontends.cli import CommandLineInterface

TOWN_MASTER: Path = Path(__file__).parent / "fixtures" / "mt_town_sample.csv"


def codes_named(codec: AddressCodec, name: str, within: str | None = None) -> list[str]:
    """List the codes of the areas that bear a name."""
    return [str(address.code) for address in codec.list_by_name(name, within=within)]


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("府中市", ["132063", "342084"]),
        ("東京都府中市", ["132063"]),
        ("広島府中市", ["342084"]),
        ("東京都", ["130001"]),
        ("東京", ["130001"]),
        ("千代田区", ["131016"]),
        ("入間郡三芳町", ["113247"]),
        ("横浜市", ["141046"]),
        ("中区", ["141046"]),
        ("横浜市中区", ["141046"]),
    ],
)
def test_prefectures_and_municipalities_are_found(
    codec: AddressCodec, name: str, expected: list[str]
) -> None:
    assert codes_named(codec, name) == expected


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("丸の内", ["131016-0011000"]),
        ("丸ノ内", ["131016-0011000"]),
        ("大曲", ["012114-0005000", "012114-0006000"]),
        ("字大曲", ["012114-0005000", "012114-0006000"]),
        ("箱塚", ["042072-0009000", "042072-0047000"]),
        ("赤石村", ["014052-0001001", "014052-0001002"]),
        ("竹間沢", ["113247-0001000"]),
        ("東", ["113247-0001001"]),
        ("大畑", ["155861-0000162"]),
        ("山の上", ["014052-0001001", "014052-0001002"]),
        ("白旗九ノ一", ["062022-0036339"]),
    ],
)
def test_oaza_and_koaza_are_found(codec: AddressCodec, name: str, expected: list[str]) -> None:
    assert codes_named(codec, name) == expected


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("府中市宮町", ["132063-0014000"]),
        ("府中市府川町", ["342084-0001000"]),
        ("東京都宮町", ["132063-0014000"]),
        ("広島県宮町", []),
        ("三芳町竹間沢", ["113247-0001000"]),
    ],
)
def test_leading_area_narrows_towns(codec: AddressCodec, name: str, expected: list[str]) -> None:
    assert codes_named(codec, name) == expected


def test_within_narrows_areas(codec: AddressCodec) -> None:
    assert codes_named(codec, "府中市", within="340006") == ["342084"]
    assert codes_named(codec, "大曲", within="012114-0006000") == ["012114-0006000"]
    assert codes_named(codec, "府中市", within="131016") == []


@pytest.mark.parametrize("name", ["丸の", "の内", "府中", "丸の内1丁目", "千代田区丸の内1-2-3"])
def test_parts_and_longer_addresses_are_not_names(codec: AddressCodec, name: str) -> None:
    assert codes_named(codec, name) == []


def test_blank_name_is_rejected(codec: AddressCodec) -> None:
    with pytest.raises(ValueError, match="blank"):
        _ = codec.list_by_name("  ")


def test_within_with_lot_numbers_is_rejected(codec: AddressCodec) -> None:
    with pytest.raises(ValueError, match="lot numbers"):
        _ = codec.list_by_name("丸の内", within="131016-0011001-2")


def test_name_command(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    database = str(tmp_path / "towns.sqlite3")
    cli = CommandLineInterface()
    assert cli.run(["--database", database, "import", str(TOWN_MASTER)]) == 0
    assert cli.run(["--database", database, "name", "府中市"]) == 0
    assert capsys.readouterr().out.splitlines()[-2:] == [
        "府中市\t132063\t東京都府中市\tMUNICIPALITY",
        "府中市\t342084\t広島県府中市\tMUNICIPALITY",
    ]
    assert cli.run(["--database", database, "name", "--output", "jsonl", "丸ノ内"]) == 0
    records: list[dict[str, object]] = [
        json.loads(line) for line in capsys.readouterr().out.splitlines()
    ]
    assert records[-1]["areas"] == [
        {"code": "131016-0011000", "address": "東京都千代田区丸の内", "level": "TOWN"}
    ]
