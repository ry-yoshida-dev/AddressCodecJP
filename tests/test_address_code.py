import pytest

from address_codec_jp import AddressCode, AddressLevel, LotNumber


def test_round_trip() -> None:
    code = AddressCode("131016", "0001001", LotNumber(2, 3))
    assert str(code) == "131016-0001001-2-3"
    assert AddressCode.parse(str(code)) == code


def test_without_lot() -> None:
    assert str(AddressCode.parse("131016-0001001")) == "131016-0001001"


def test_levels() -> None:
    assert AddressCode.parse("130001").level is AddressLevel.PREFECTURE
    assert AddressCode.parse("131067").level is AddressLevel.MUNICIPALITY
    assert AddressCode.parse("131067-0004000").level is AddressLevel.TOWN
    assert AddressCode.parse("131067-0004001-2").level is AddressLevel.BLOCK
    assert AddressCode.parse("131067-0004001-2-3").level is AddressLevel.RESIDENCE
    assert str(AddressCode.for_prefecture("01")) == "010006"
    assert str(AddressCode.for_prefecture("47")) == "470007"


@pytest.mark.parametrize(
    "text",
    [
        "131017-0001001",
        "13101-0001001",
        "131016-001001",
        "abc",
        "130001-0001001",
        "131016--1",
        "131016-0011001-01",
        "131016-0011001-0",
    ],
)
def test_rejects_invalid(text: str) -> None:
    with pytest.raises(ValueError, match=r"address code|check digit|prefecture code"):
        _ = AddressCode.parse(text)


def test_parse_accepts_full_width_text() -> None:
    assert str(AddressCode.parse("１３１０６７－０００４００１－２")) == "131067-0004001-2"


@pytest.mark.parametrize(
    ("code", "lineage"),
    [
        (
            "131067-0004001-2-3",
            [
                "131067-0004001-2-3",
                "131067-0004001-2",
                "131067-0004001",
                "131067-0004000",
                "131067",
                "130001",
            ],
        ),
        ("131067-0004000-2", ["131067-0004000-2", "131067-0004000", "131067", "130001"]),
        ("130001", ["130001"]),
    ],
)
def test_lineage_lists_enclosing_areas(code: str, lineage: list[str]) -> None:
    assert [str(item) for item in AddressCode.parse(code).lineage()] == lineage
    assert AddressCode.for_prefecture("13").parent is None


def test_rejects_residence_without_block() -> None:
    with pytest.raises(ValueError, match="requires a block"):
        _ = LotNumber(block=None, residence=3)


def test_rejects_lot_without_town() -> None:
    with pytest.raises(ValueError, match="require a machiaza_id"):
        _ = AddressCode("131016", None, LotNumber(1))
