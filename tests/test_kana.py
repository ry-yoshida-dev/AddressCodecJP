import pytest

from address_codec_jp import (
    AddressCodec,
    AddressFormat,
    DigitWidth,
    LotStyle,
    NameScript,
    NumeralStyle,
)

KANA: AddressFormat = AddressFormat(name_script=NameScript.KATAKANA)


@pytest.mark.parametrize(
    ("code", "address_format", "expected"),
    [
        ("130001", KANA, "トウキョウト"),
        ("131067", KANA, "トウキョウトタイトウク"),
        ("131016-0001001-2-3", KANA, "トウキョウトチヨダクマルノウチ1チョウメ2バン3ゴウ"),
        (
            "131016-0001001-2-3",
            AddressFormat(name_script=NameScript.KATAKANA, lot_style=LotStyle.LAND_PARCEL),
            "トウキョウトチヨダクマルノウチ1チョウメ2バンチ3",
        ),
        (
            "131016-0001001-2-3",
            AddressFormat(name_script=NameScript.KATAKANA, lot_style=LotStyle.HYPHEN),
            "トウキョウトチヨダクマルノウチ1-2-3",
        ),
        (
            "131016-0001001-2-3",
            AddressFormat(
                name_script=NameScript.KATAKANA,
                numeral_style=NumeralStyle.KANJI,
                is_prefecture_included=False,
            ),
            "チヨダクマルノウチ一チョウメ二バン三ゴウ",
        ),
        ("012025-0007001-4", KANA, "ホッカイドウハコダテシベンテンチョウ1チョウ4バンチ"),
        ("113247-0001001-5", KANA, "サイタマケンイルマグンミヨシマチチクマザワヒガシ5バンチ"),
        (
            "162019-0000590",
            AddressFormat(name_script=NameScript.KATAKANA, digit_width=DigitWidth.FULL),
            "トヤマケントヤマシササヅ７ク",
        ),
        ("141046-0001000", KANA, "カナガワケンヨコハマシナカクヤマシタチョウ"),
        ("131067-0001000", KANA, "トウキョウトタイトウクアサクサバシ"),
    ],
)
def test_decode_writes_katakana_readings(
    codec: AddressCodec, code: str, address_format: AddressFormat, expected: str
) -> None:
    assert codec.decode(code, address_format) == expected


def test_missing_reading_raises(codec: AddressCodec) -> None:
    with pytest.raises(LookupError, match="no reading"):
        _ = codec.decode("042072-0009000", KANA)
    assert codec.decode("042072-0009000") == "宮城県名取市箱塚"
