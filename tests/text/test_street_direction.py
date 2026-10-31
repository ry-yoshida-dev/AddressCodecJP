import pytest

from address_codec_jp import (
    AddressCode,
    AddressCodec,
    AddressFormat,
    AddressLevel,
    AddressNotFoundError,
    AmbiguousAddressError,
    MatchTier,
    NameScript,
)


@pytest.mark.parametrize(
    ("address", "expected"),
    [
        ("京都市下京区烏丸通塩小路下る東塩小路町", "261068-0416115"),
        ("京都市下京区東塩小路町烏丸通塩小路下る", "261068-0416115"),
        ("京都市下京区烏丸通塩小路上る西入東塩小路町", "261068-0416114"),
        ("京都府京都市中京区烏丸通御池上る二条殿町", "261041-0369102"),
        ("中京区竹屋町通烏丸西入亀屋町", "261041-0102102"),
        ("中京区竹屋町通柳馬場西入四丁目", "261041-1337102"),
    ],
)
def test_street_direction_before_or_after_the_oaza_is_its_koaza(
    codec: AddressCodec, address: str, expected: str
) -> None:
    assert str(codec.encode(address)) == expected


@pytest.mark.parametrize(
    ("address", "expected"),
    [
        ("京都市下京区烏丸通塩小路下る東塩小路町721", "261068-0416000-721"),
        ("京都市下京区東塩小路町烏丸通塩小路下る721番地", "261068-0416000-721"),
        ("京都市中京区烏丸通御池上る二条殿町552", "261041-0369000-552"),
        ("中京区竹屋町通烏丸西入亀屋町12-3", "261041-0102000-12-3"),
        ("中京区竹屋町通柳馬場西入四丁目5", "261041-1337000-5"),
    ],
)
def test_lot_numbers_belong_to_the_oaza_of_the_street_direction(
    codec: AddressCodec, address: str, expected: str
) -> None:
    assert str(codec.encode(address)) == expected


@pytest.mark.parametrize(
    ("address", "expected"),
    [
        ("中京区烏丸通竹屋町西入亀屋町3", "261041-1355102-3"),
        ("東山区大和大路通正面下る大和大路5", "261050-0101102-5"),
    ],
)
def test_street_direction_without_registered_oaza_keeps_its_lot_numbers(
    codec: AddressCodec, address: str, expected: str
) -> None:
    assert str(codec.encode(address)) == expected


def test_lot_numbers_of_a_street_direction_under_a_complemented_oaza_stay_on_it(
    located_codec: AddressCodec,
) -> None:
    with pytest.raises(AddressNotFoundError, match="261050-0101102-5"):
        located_codec.verify_lot(AddressCode.parse("261050-0101102-5"))


@pytest.mark.parametrize(
    "address",
    [
        "京都市下京区烏丸通塩小路下ル東塩小路町",
        "京都市下京区烏丸通り塩小路下がる東塩小路町",
        "京都市下京区東塩小路町烏丸通塩小路下ル",
    ],
)
def test_notation_variants_of_a_street_direction_are_folded(
    codec: AddressCodec, address: str
) -> None:
    address_match = codec.match(address)
    assert str(address_match.code) == "261068-0416115"
    assert address_match.town_name_tier is MatchTier.FOLDED


def test_variant_with_repeated_directions_and_lot_numbers(codec: AddressCodec) -> None:
    address_match = codec.match("下京区烏丸通り塩小路上がる西入ル東塩小路町8-1 2階")
    assert str(address_match.code) == "261068-0416000-8-1"
    assert address_match.remainder == "2階"


def test_street_direction_decides_between_oaza_of_the_same_name(codec: AddressCodec) -> None:
    assert str(codec.encode("中京区釜座通竹屋町上る亀屋町5")) == "261041-0106000-5"
    with pytest.raises(AmbiguousAddressError) as raised:
        _ = codec.encode("中京区亀屋町5")
    assert [str(code) for code in raised.value.candidates] == [
        "261041-0102000-5",
        "261041-0106000-5",
    ]


@pytest.mark.parametrize(
    ("address", "expected"),
    [
        ("中京区烏丸通竹屋町上る亀屋町5", "261041-0102000-5"),
        ("中京区釜座通夷川上る亀屋町", "261041-0106000"),
        ("中京区丸太町通柳馬場東入四丁目5", "261041-1337000-5"),
    ],
)
def test_unregistered_street_direction_selects_the_most_similar_oaza(
    codec: AddressCodec, address: str, expected: str
) -> None:
    address_match = codec.match(address)
    assert str(address_match.code) == expected
    assert address_match.town_name_tier is MatchTier.FOLDED


@pytest.mark.parametrize(
    ("address", "expected"),
    [
        ("京都市烏丸通塩小路下る東塩小路町", "261068-0416115"),
        ("烏丸通塩小路下る東塩小路町", "261068-0416115"),
        ("京都府烏丸通塩小路下る東塩小路町721", "261068-0416000-721"),
        ("竹屋町通烏丸西入亀屋町12-3", "261041-0102000-12-3"),
        ("烏丸通り塩小路下ル東塩小路町", "261068-0416115"),
    ],
)
def test_street_direction_is_read_without_the_ward(
    codec: AddressCodec, address: str, expected: str
) -> None:
    assert str(codec.encode(address)) == expected


def test_street_direction_without_the_ward_respects_within(codec: AddressCodec) -> None:
    with pytest.raises(AddressNotFoundError):
        _ = codec.encode("烏丸通塩小路下る東塩小路町", within="261041")


@pytest.mark.parametrize("code", ["261068-0416115-538-1", "261068-0416000-538-1"])
def test_lot_numbers_of_a_street_direction_are_located_on_its_oaza(
    located_codec: AddressCodec, code: str
) -> None:
    location = located_codec.locate_code(code)
    assert str(location.code) == "261068-0416000-538-1"
    assert location.level is AddressLevel.RESIDENCE
    assert location.is_exact
    located_codec.verify_lot(AddressCode.parse(code))
    assert located_codec.has_parcel_shape(code)


def test_unregistered_lot_numbers_of_a_street_direction_fail_verification(
    located_codec: AddressCodec,
) -> None:
    with pytest.raises(AddressNotFoundError, match="261068-0416000-538-2"):
        located_codec.verify_lot(AddressCode.parse("261068-0416115-538-2"))


@pytest.mark.parametrize(
    "address",
    [
        "中京区ほげ通ふが上る亀屋町",
        "中京区あいうえお北側亀屋町",
        "あいうえお北側亀屋町1",
    ],
)
def test_direction_without_a_shared_street_name_is_not_read(
    codec: AddressCodec, address: str
) -> None:
    with pytest.raises(AddressNotFoundError):
        _ = codec.encode(address)


def test_street_direction_is_not_read_outside_kyoto(codec: AddressCodec) -> None:
    with pytest.raises(AddressNotFoundError):
        _ = codec.encode("千代田区烏丸通塩小路下る丸の内1丁目")


@pytest.mark.parametrize(
    ("code", "address_format", "expected"),
    [
        ("261068-0416115", AddressFormat(), "京都府京都市下京区烏丸通塩小路下る東塩小路町"),
        (
            "261041-1355102-3",
            AddressFormat(),
            "京都府京都市中京区烏丸通竹屋町西入亀屋町3番地",
        ),
        (
            "261068-0416115",
            AddressFormat(name_script=NameScript.KATAKANA),
            "キョウトフキョウトシシモギョウクカラスマドオリシオコウジサガルヒガシシオコウジチョウ",
        ),
    ],
)
def test_street_direction_is_written_before_the_oaza(
    codec: AddressCodec, code: str, address_format: AddressFormat, expected: str
) -> None:
    assert codec.decode(code, address_format) == expected


def test_town_records_whether_its_koaza_is_a_street_direction(codec: AddressCodec) -> None:
    street = codec.resolve("261068-0416115").town
    oaza = codec.resolve("261068-0416000").town
    assert street is not None
    assert oaza is not None
    assert (street.is_street_direction, oaza.is_street_direction) == (True, False)
