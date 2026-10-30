from pathlib import Path

import pytest

from address_codec_jp import (
    AddressCodec,
    AddressNotFoundError,
    AmbiguousAddressError,
    RegistryImporter,
)

TOWN_MASTER_HEADER: str = (
    "lg_code,machiaza_id,pref,county,city,ward,oaza_cho,chome,koaza,"
    + "pref_kana,county_kana,city_kana,ward_kana,oaza_cho_kana,chome_kana,koaza_kana,"
    + "post_code,ablt_date,rsdt_addr_flg\n"
)


@pytest.mark.parametrize(
    ("within", "expected"),
    [("130001", "132063"), ("340006", "342084"), ("342084", "342084")],
)
def test_within_decides_shared_municipality_name(
    codec: AddressCodec, within: str, expected: str
) -> None:
    assert str(codec.encode("府中市", within=within)) == expected


def test_within_rejects_address_outside(codec: AddressCodec) -> None:
    with pytest.raises(AddressNotFoundError):
        _ = codec.encode("千代田区丸の内1-1", within="340006")
    with pytest.raises(AddressNotFoundError):
        _ = codec.encode("東京都", within="131016")


def test_within_restricts_towns(codec: AddressCodec) -> None:
    assert str(codec.encode("千代田区丸の内1-1", within="131016-0011000")) == "131016-0011001-1"
    with pytest.raises(AddressNotFoundError):
        _ = codec.encode("千代田区丸の内1-1", within="131016-0002001")


def test_within_keeps_ward_of_designated_city_required(codec: AddressCodec) -> None:
    with pytest.raises(AmbiguousAddressError):
        _ = codec.encode("横浜市", within="141046")
    assert str(codec.encode("横浜市山下町", within="140007")) == "141046-0001000"


def test_within_must_not_have_lot_numbers(codec: AddressCodec) -> None:
    with pytest.raises(ValueError, match="lot numbers"):
        _ = codec.encode("府中市", within="131016-0011001-1")


def test_group_decides_ambiguous_address_by_common_area(codec: AddressCodec) -> None:
    group = codec.match_group(["千代田区丸の内1-1", "府中市"])
    assert str(group.area) == "130001"
    assert [str(item.code) for item in group.matches] == ["131016-0011001-1", "132063"]


def test_group_area_is_narrowest_enclosing_area(codec: AddressCodec) -> None:
    group = codec.match_group(["丸の内1丁目1", "丸の内2丁目1"])
    assert str(group.area) == "131016-0011000"
    group = codec.match_group(["千代田区丸の内1-1", "千代田区霞が関1-1"])
    assert str(group.area) == "131016"


def test_group_decides_town_without_municipality(tmp_path: Path) -> None:
    master = tmp_path / "master.csv"
    _ = master.write_text(
        TOWN_MASTER_HEADER
        + "469017,0001000,試験県,,北市,,山田,,,,,,,,,,,,0\n"
        + "469025,0001000,試験県,,南市,,山田,,,,,,,,,,,,0\n"
        + "469025,0002000,試験県,,南市,,川原,,,,,,,,,,,,0\n",
        encoding="utf-8",
    )
    with RegistryImporter.open(":memory:") as importer:
        _ = importer.import_file(master)
        codec = AddressCodec(importer.database)
        group = codec.match_group(["山田1-2", "川原1-2"])
        assert str(group.area) == "469025"
        assert [str(item.code) for item in group.matches] == [
            "469025-0001000-1-2",
            "469025-0002000-1-2",
        ]


def test_group_fails_without_unique_common_area(codec: AddressCodec) -> None:
    with pytest.raises(AmbiguousAddressError) as raised:
        _ = codec.match_group(["府中市"])
    assert [str(code) for code in raised.value.candidates] == ["132063", "342084"]


def test_group_fails_without_common_area(codec: AddressCodec) -> None:
    with pytest.raises(AddressNotFoundError, match="encloses every address"):
        _ = codec.match_group(["千代田区丸の内1-1", "府中市", "横浜市中区山下町"])


def test_group_decides_koaza_by_common_town(codec: AddressCodec) -> None:
    group = codec.match_group(["神恵内村赤石村山之上", "神恵内村赤石村字山の上"])
    assert str(group.area) == "014052-0001001"
    assert [str(item.code) for item in group.matches] == ["014052-0001001"] * 2


def test_group_fails_when_address_stays_ambiguous_in_common_area(codec: AddressCodec) -> None:
    with pytest.raises(AmbiguousAddressError) as raised:
        _ = codec.match_group(["神恵内村赤石村山之上"])
    assert [str(code) for code in raised.value.candidates] == ["014052-0001001", "014052-0001002"]


def test_group_does_not_read_designated_city_as_ward(codec: AddressCodec) -> None:
    with pytest.raises(AmbiguousAddressError):
        _ = codec.match_group(["横浜市", "横浜市中区山下町"])


def test_group_fails_when_address_is_not_found(codec: AddressCodec) -> None:
    with pytest.raises(AddressNotFoundError):
        _ = codec.match_group(["千代田区丸の内1-1", "存在しない市"])


@pytest.mark.parametrize("addresses", [[], ["千代田区丸の内1-1", " "]])
def test_group_rejects_empty_input(codec: AddressCodec, addresses: list[str]) -> None:
    with pytest.raises(ValueError, match=r"(?i)address"):
        _ = codec.match_group(addresses)
