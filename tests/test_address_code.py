import pytest

from address_codec_jp import AddressCode, AddressLevel, LotNumber, Prefecture


def test_round_trip() -> None:
    code = AddressCode("131016", "0011001", LotNumber(2, 3))
    assert str(code) == "131016-0011001-2-3"
    assert AddressCode.parse(str(code)) == code


def test_without_lot() -> None:
    assert str(AddressCode.parse("131016-0011001")) == "131016-0011001"


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


@pytest.mark.parametrize(
    ("code", "is_oaza"),
    [
        ("131067-0004000", True),
        ("131067-0004001", False),
        ("131067-0004000-2", False),
        ("131067", False),
        ("130001", False),
    ],
)
def test_is_oaza_tells_oaza_level_towns(code: str, is_oaza: bool) -> None:
    assert AddressCode.parse(code).is_oaza is is_oaza


def test_rejects_residence_without_block() -> None:
    with pytest.raises(ValueError, match="requires a block"):
        _ = LotNumber(block=None, residence=3)


def test_rejects_lot_without_town() -> None:
    with pytest.raises(ValueError, match="require a machiaza_id"):
        _ = AddressCode("131016", None, LotNumber(1))


@pytest.mark.parametrize(
    ("outer", "inner", "is_contained"),
    [
        ("130001", "131067-0004001-2-3", True),
        ("131067", "131067-0004001-2", True),
        ("131067-0004000", "131067-0004001", True),
        ("131067-0004001-2", "131067-0004001-2-3", True),
        ("131067-0004001", "131067-0004001", True),
        ("131067-0004001-2-3", "131067-0004001-2", False),
        ("131067-0004002", "131067-0004001-2", False),
        ("140007", "131067", False),
    ],
)
def test_contains(outer: str, inner: str, is_contained: bool) -> None:
    assert AddressCode.parse(outer).contains(AddressCode.parse(inner)) is is_contained


@pytest.mark.parametrize("code", ["00", "48", "1", "ab"])
def test_prefecture_rejects_invalid_codes(code: str) -> None:
    with pytest.raises(ValueError, match="01 to 47"):
        _ = Prefecture(code=code, name="", kana="")
