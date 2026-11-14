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
from address_codec_jp.text.matching.reading import StreetDirectionReader
from address_codec_jp.text.normalization import TextNormalizer
from tests.text.counting_normalizer import CountingNormalizer


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
        ("京都市下京区烏丸通塩小路下る東塩小路町721", "261068-0416000-p721"),
        ("京都市下京区東塩小路町烏丸通塩小路下る721番地", "261068-0416000-p721"),
        ("京都市中京区烏丸通御池上る二条殿町552", "261041-0369000-p552"),
        ("中京区竹屋町通烏丸西入亀屋町12-3", "261041-0102000-p12-3"),
        ("中京区竹屋町通柳馬場西入四丁目5", "261041-1337000-p5"),
    ],
)
def test_lot_numbers_belong_to_the_oaza_of_the_street_direction(
    codec: AddressCodec, address: str, expected: str
) -> None:
    assert str(codec.encode(address)) == expected


@pytest.mark.parametrize(
    ("address", "expected"),
    [
        ("中京区烏丸通竹屋町西入亀屋町3", "261041-1355102-p3"),
        ("東山区大和大路通正面下る大和大路5", "261050-0101102-p5"),
    ],
)
def test_street_direction_without_registered_oaza_keeps_its_lot_numbers(
    codec: AddressCodec, address: str, expected: str
) -> None:
    assert str(codec.encode(address)) == expected


def test_lot_numbers_of_a_street_direction_under_a_complemented_oaza_stay_on_it(
    located_codec: AddressCodec,
) -> None:
    with pytest.raises(AddressNotFoundError, match="261050-0101102-p5"):
        located_codec.verify_lot(AddressCode.parse("261050-0101102-p5"))


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
    assert str(address_match.code) == "261068-0416000-p8-1"
    assert address_match.remainder == "2階"


def test_street_direction_decides_between_oaza_of_the_same_name(codec: AddressCodec) -> None:
    assert str(codec.encode("中京区釜座通竹屋町上る亀屋町5")) == "261041-0106000-p5"
    with pytest.raises(AmbiguousAddressError) as raised:
        _ = codec.encode("中京区亀屋町5")
    assert [str(code) for code in raised.value.candidates] == [
        "261041-0102000-p5",
        "261041-0106000-p5",
    ]


@pytest.mark.parametrize(
    ("address", "expected"),
    [
        ("中京区烏丸通竹屋町上る亀屋町5", "261041-0102000-p5"),
        ("中京区釜座通夷川上る亀屋町", "261041-0106000"),
        ("中京区丸太町通柳馬場東入四丁目5", "261041-1337000-p5"),
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
        ("京都府烏丸通塩小路下る東塩小路町721", "261068-0416000-p721"),
        ("竹屋町通烏丸西入亀屋町12-3", "261041-0102000-p12-3"),
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


@pytest.mark.parametrize("code", ["261068-0416115-p538-1", "261068-0416000-p538-1"])
def test_lot_numbers_of_a_street_direction_are_located_on_its_oaza(
    located_codec: AddressCodec, code: str
) -> None:
    location = located_codec.locate_code(code)
    assert str(location.code) == code
    assert str(location.located_code) == code
    assert location.coordinate == located_codec.locate_code("261068-0416000-p538-1").coordinate
    assert location.level is AddressLevel.RESIDENCE
    assert location.is_exact
    located_codec.verify_lot(AddressCode.parse(code))
    assert located_codec.has_parcel_shape(code)


def test_unregistered_lot_numbers_of_a_street_direction_fail_verification(
    located_codec: AddressCodec,
) -> None:
    with pytest.raises(AddressNotFoundError, match="261068-0416115-p538-2"):
        located_codec.verify_lot(AddressCode.parse("261068-0416115-p538-2"))


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
            "261041-1355102-p3",
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


def test_lot_numbers_lie_within_their_street_direction(located_codec: AddressCodec) -> None:
    address = "京都市下京区烏丸通塩小路下る東塩小路町538番地1"
    within = "261068-0416115"
    assert str(located_codec.encode(address, within=within)) == "261068-0416000-p538-1"
    verified = located_codec.encode(address, within=within, is_lot_verified=True)
    assert str(verified) == "261068-0416000-p538-1"
    assert str(located_codec.encode("烏丸通塩小路下る東塩小路町", within=within)) == within
    with pytest.raises(AddressNotFoundError, match="does not lie within"):
        _ = located_codec.encode("京都市下京区東塩小路町", within=within)


def test_text_after_a_street_direction_is_not_scanned(codec: AddressCodec) -> None:
    town = codec.resolve("261068-0416115").town
    assert town is not None
    normalizer = CountingNormalizer()
    reader = StreetDirectionReader(normalizer)
    text = TextNormalizer().normalize("烏丸通塩小路下る" * 400)
    split_points = reader.split_points(text, reader.fold_names([town]))
    street_matches = reader.match_all(text, [town])
    assert split_points[0] == len("烏丸通塩小路下る")
    assert split_points[-1] < len(text) // 10
    assert [candidates.towns for candidates in street_matches] == [[town]]
    assert normalizer.fold_count < 200
