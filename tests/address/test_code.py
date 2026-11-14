import pytest

from address_codec_jp import AddressCode, AddressLevel, LotNumber, LotSystem, Prefecture


def test_round_trip() -> None:
    code = AddressCode("131016", "0011001", LotNumber(2, 3, system=LotSystem.RESIDENCE_INDICATION))
    assert str(code) == "131016-0011001-2-3"
    assert AddressCode.parse(str(code)) == code


@pytest.mark.parametrize(
    ("text", "numbers", "system"),
    [
        ("113247-0001000-p124", [124], LotSystem.LAND_PARCEL),
        ("113247-0001000-p124-1-1", [124, 1, 1], LotSystem.LAND_PARCEL),
        ("113247-0001000-P124-1", [124, 1], LotSystem.LAND_PARCEL),
        ("131016-0011001-2-3-4", [2, 3, 4], LotSystem.RESIDENCE_INDICATION),
    ],
)
def test_lot_numbers_carry_their_numbering_system(
    text: str, numbers: list[int], system: LotSystem
) -> None:
    code = AddressCode.parse(text)
    assert code.lot.numbers == numbers
    assert code.lot.system is system
    assert str(code) == text.replace("P", "p")


def test_land_parcel_and_residence_with_the_same_numbers_differ() -> None:
    parcel = AddressCode.parse("131016-0011001-p2-3")
    residence = AddressCode.parse("131016-0011001-2-3")
    assert parcel != residence
    assert parcel.lot.numbers == residence.lot.numbers


@pytest.mark.parametrize("dash", ["‐", "−", "－", "ー"])
def test_parse_accepts_dash_variants(dash: str) -> None:
    text = dash.join(["131016", "0011001", "2", "3"])
    assert str(AddressCode.parse(text)) == "131016-0011001-2-3"


@pytest.mark.parametrize(
    ("code", "parent"),
    [
        ("131016-0011001-2-3-4", "131016-0011001-2-3"),
        ("131016-0011001-2-3", "131016-0011001-2"),
        ("113247-0001000-p123-9", "113247-0001000"),
        ("113247-0001000-p123-4-1", "113247-0001000"),
        ("155861-0000162", "155861"),
        ("113247-0001001", "113247-0001000"),
    ],
)
def test_parent(code: str, parent: str) -> None:
    found = AddressCode.parse(code).parent
    assert found is not None
    assert str(found) == parent


def test_parcel_branch_is_not_inside_the_original_parcel() -> None:
    assert not AddressCode.parse("113247-0001000-p123").contains(
        AddressCode.parse("113247-0001000-p123-9")
    )


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
        ("011011-0001000", ["011011-0001000", "011011", "011002", "010006"]),
        ("011100", ["011100", "011002", "010006"]),
        ("011002", ["011002", "010006"]),
        ("141313", ["141313", "141305", "140007"]),
        ("141186", ["141186", "141003", "140007"]),
        ("221384", ["221384", "221309", "220001"]),
        ("012025", ["012025", "010006"]),
        ("131237", ["131237", "130001"]),
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


def test_rejects_oversized_lot_numbers() -> None:
    with pytest.raises(ValueError, match="must not exceed"):
        _ = AddressCode.parse("131016-0011001-99999999999999999999")


def test_rejects_lot_without_town() -> None:
    with pytest.raises(ValueError, match="require a machiaza_id"):
        _ = AddressCode("131016", None, LotNumber(1, system=LotSystem.RESIDENCE_INDICATION))


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
