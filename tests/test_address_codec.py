from pathlib import Path

import pytest

from address_codec_jp import (
    AddressCode,
    AddressCodec,
    AddressFormat,
    AddressLevel,
    DigitWidth,
    LotStyle,
    NumeralStyle,
)


@pytest.mark.parametrize(
    ("address", "expected"),
    [
        ("東京都千代田区丸の内１丁目２番３号", "131016-0001001-2-3"),
        ("千代田区丸の内一丁目二番三号", "131016-0001001-2-3"),
        ("東京都千代田区丸の内1-2-3", "131016-0001001-2-3"),
        ("東京都 千代田区 丸の内 １－２－３", "131016-0001001-2-3"),
        ("千代田区丸ノ内1ー2ー3", "131016-0001001-2-3"),
        ("千代田区丸の内1‐2−3", "131016-0001001-2-3"),
        ("千代田区丸の内一の二の三", "131016-0001001-2-3"),
        ("千代田区丸の内2丁目", "131016-0001002"),
        ("東京都千代田区霞ヶ関1-2", "131016-0002001-2"),
        ("千代田区一番町5", "131016-0003000-5"),
        ("〒354-0044 埼玉県入間郡三芳町竹間沢123-4", "113247-0001000-123-4"),
        ("埼玉県三芳町大字竹間沢123番地の4", "113247-0001000-123-4"),
        ("三芳町竹間沢字東12", "113247-0001001-12"),
        ("横浜市中区山下町279", "141046-0001000-279"),
        ("北海道札幌市中央区北1条西1丁目2", "011011-0001001-2"),
        ("札幌市中央区北一条西一丁目", "011011-0001001"),
        ("東京都府中市宮町1-1", "132063-0001001-1"),
        ("府中市宮町1-1", "132063-0001001-1"),
        ("広島県府中市府川町5", "342084-0001000-5"),
        ("東京千代田区丸の内1-2-3", "131016-0001001-2-3"),
        ("東京", "130001"),
        ("横浜市山下町279", "141046-0001000-279"),
        ("神奈川横浜市山下町279", "141046-0001000-279"),
        ("千代田区丸の内一丁目十二番地三", "131016-0001001-12-3"),
        ("千代田区丸の内1丁目12番三", "131016-0001001-12-3"),
        ("米沢市大字三沢字白旗九ノ一十二番三号", "062022-0036339-12-3"),
        ("石巻市根岸字城見の一十二番三号", "042021-0093103-12-3"),
        ("東京都台東区浅草橋", "131067-0001000"),
        ("台東区浅草橋5丁目", "131067-0001005"),
        ("台東区浅草橋5-1-1", "131067-0001005-1-1"),
        ("千代田区丸の内", "131016-0001000"),
        ("東京都", "130001"),
        ("米沢市大字三沢字白旗九ノ一12番3号", "062022-0036339-12-3"),
        ("米沢市三沢白旗九ノ一", "062022-0036339"),
        ("米沢市三沢白旗12番3号", "062022-0036338-12-3"),
        ("山形市流通センタ－1丁目12番3号", "062014-0389001-12-3"),
        ("山形市流通センター1丁目12番3号", "062014-0389001-12-3"),
        ("山形市流通センター", "062014-0389000"),
        ("〒100‐0005 東京都千代田区丸の内1-2-3", "131016-0001001-2-3"),
        ("輪島市門前町本市１ 12番3号", "172049-0196110-12-3"),
        ("石巻市根岸字城見の一12番3号", "042021-0093103-12-3"),
        ("粟島浦村字大畑12番3号", "155861-0000162-12-3"),
        ("富山市笹津７区12番3号", "162019-0000590-12-3"),
        ("富山市笹津7-12", "162019-0258000-7-12"),
        ("輪島市門前町椎木12番3号", "172049-0144000-12-3"),
        ("志賀町福井八12番3号", "173843-0089134-12-3"),
        ("志賀町福井12-3", "173843-0089000-12-3"),
        ("名古屋市北区芦辺町三丁目12番3号", "231037-0001103-12-3"),
        ("名古屋市北区芦辺町12番3号", "231037-0001000-12-3"),
        ("網走市大曲1", "012114-0005000-1"),
        ("網走市字大曲1", "012114-0006000-1"),
        ("神恵内村大字赤石村字山の上1", "014052-0001001-1"),
        ("神恵内村赤石村山ノ上1", "014052-0001002-1"),
        ("東京都台東区", "131067"),
        ("台東区", "131067"),
        ("入間郡三芳町", "113247"),
        ("北海道札幌市中央区", "011011"),
        ("函館市弁天町1丁", "012025-0007001"),
        ("函館市弁天町1丁目2", "012025-0007001-2"),
    ],
)
def test_encode(codec: AddressCodec, address: str, expected: str) -> None:
    assert str(codec.encode(address)) == expected


def test_match_keeps_building_name_without_lot(codec: AddressCodec) -> None:
    address_match = codec.match("台東区浅草 浅草ビル")
    assert str(address_match.code) == "131067-0012000"
    assert address_match.remainder == "浅草ビル"


def test_match_keeps_building_name(codec: AddressCodec) -> None:
    address_match = codec.match("港区六本木6-10-1 六本木ヒルズ森タワー")
    assert str(address_match.code) == "131032-0005006-10-1"
    assert address_match.remainder == "六本木ヒルズ森タワー"


@pytest.mark.parametrize(
    "address",
    [
        "府中市",
        "府中市存在しない町1",
        "横浜市",
        "神奈川県横浜市",
        "輪島市門前町椎木12-3",
        "千代田区丸の内9丁目",
        "千代田区一番町1丁目",
        "千代田区存在しない町1",
        "架空市1-1",
        "東京都架空市",
        "網走市大字大曲1",
        "神恵内村赤石村山之上1",
        "名取市箱塚12番3号",
        "山形市流通センター12番3号",
        "千代田区丸の内9-1-2",
        "台東区浅草橋6-1-1",
        "台東区浅草橋9丁目",
        "台東区浅草橋12",
        "輪島市門前町本市112番3号",
        "名古屋市北区芦辺町五丁目",
    ],
)
def test_encode_rejects_unmatched(codec: AddressCodec, address: str) -> None:
    with pytest.raises(LookupError):
        _ = codec.encode(address)


def test_encode_rejects_blank(codec: AddressCodec) -> None:
    with pytest.raises(ValueError):
        _ = codec.encode("　")


@pytest.mark.parametrize(
    ("address_format", "expected"),
    [
        (AddressFormat(), "東京都千代田区丸の内1丁目2番3号"),
        (AddressFormat(numeral_style=NumeralStyle.KANJI), "東京都千代田区丸の内一丁目二番三号"),
        (AddressFormat(lot_style=LotStyle.HYPHEN), "東京都千代田区丸の内1-2-3"),
        (AddressFormat(lot_style=LotStyle.LAND_PARCEL), "東京都千代田区丸の内1丁目2番地3"),
        (
            AddressFormat(lot_style=LotStyle.HYPHEN, digit_width=DigitWidth.FULL),
            "東京都千代田区丸の内１－２－３",
        ),
        (AddressFormat(is_prefecture_included=False), "千代田区丸の内1丁目2番3号"),
    ],
)
def test_decode_formats(codec: AddressCodec, address_format: AddressFormat, expected: str) -> None:
    assert codec.decode("131016-0001001-2-3", address_format) == expected


def test_decode_county_and_koaza(codec: AddressCodec) -> None:
    assert codec.decode("113247-0001001-12") == "埼玉県入間郡三芳町竹間沢東12番"
    assert (
        codec.decode(
            "113247-0001000-123-4",
            AddressFormat(is_county_included=False, lot_style=LotStyle.LAND_PARCEL),
        )
        == "埼玉県三芳町竹間沢123番地4"
    )


def test_decode_oaza_level(codec: AddressCodec) -> None:
    assert codec.decode("131067-0001000") == "東京都台東区浅草橋"


def test_decode_prefecture_and_municipality(codec: AddressCodec) -> None:
    assert codec.decode("130001") == "東京都"
    assert codec.decode("131067") == "東京都台東区"
    assert codec.decode("131067", AddressFormat(is_prefecture_included=False)) == "台東区"
    assert codec.decode("113247", AddressFormat(is_county_included=False)) == "埼玉県三芳町"


def test_decode_keeps_short_chome_suffix(codec: AddressCodec) -> None:
    assert codec.decode("012025-0007001-2") == "北海道函館市弁天町1丁2番"


def test_levels(codec: AddressCodec) -> None:
    assert codec.encode("東京都").level is AddressLevel.PREFECTURE
    assert codec.encode("台東区").level is AddressLevel.MUNICIPALITY
    assert codec.encode("台東区浅草橋").level is AddressLevel.TOWN


def test_registered_oaza_town_is_kept(codec: AddressCodec) -> None:
    assert str(codec.encode("三芳町竹間沢")) == "113247-0001000"


def test_decode_rejects_lot_on_complemented_oaza(codec: AddressCodec) -> None:
    assert codec.decode("131067-0001000") == "東京都台東区浅草橋"
    with pytest.raises(ValueError):
        _ = codec.decode("131067-0001000-1-2")


def test_decode_half_width_normalizes_registry_digits(codec: AddressCodec) -> None:
    assert codec.decode("162019-0000590-12-3") == "富山県富山市笹津7区12番3号"
    assert (
        codec.decode("162019-0000590-12-3", AddressFormat(digit_width=DigitWidth.FULL))
        == "富山県富山市笹津７区１２番３号"
    )


def test_decode_kanji_large_lot(codec: AddressCodec) -> None:
    decoded = codec.decode("113247-0001000-12345", AddressFormat(numeral_style=NumeralStyle.KANJI))
    assert decoded == "埼玉県入間郡三芳町竹間沢一二三四五番"


def test_decode_unknown_town(codec: AddressCodec) -> None:
    with pytest.raises(KeyError):
        _ = codec.decode("131016-9999999")


def test_round_trip(codec: AddressCodec) -> None:
    code = codec.encode("北海道札幌市中央区北一条西一丁目2番3号")
    assert codec.decode(code) == "北海道札幌市中央区北一条西1丁目2番3号"
    assert codec.encode(codec.decode(code, AddressFormat(numeral_style=NumeralStyle.KANJI))) == code


def test_reimport_refreshes_matching(tmp_path: Path) -> None:
    master = tmp_path / "master.csv"
    _ = master.write_text(
        "lg_code,machiaza_id,pref,county,city,ward,oaza_cho,chome,koaza\n"
        + "131067,0012000,東京都,,台東区,,浅草,,\n",
        encoding="utf-8",
    )
    with AddressCodec.create(":memory:") as codec:
        _ = codec.import_town_master(master)
        assert str(codec.encode("台東区浅草")) == "131067-0012000"
        _ = master.write_text(
            "lg_code,machiaza_id,pref,county,city,ward,oaza_cho,chome,koaza\n"
            + "131067,0001001,東京都,,台東区,,浅草橋,一丁目,\n",
            encoding="utf-8",
        )
        _ = codec.import_town_master(master)
        with pytest.raises(LookupError):
            _ = codec.encode("台東区浅草")


AMBIGUOUS_TOWN_CODES: frozenset[str] = frozenset(
    {
        "042072-0009000",
        "042072-0047000",
        "172049-0144000",
        "172049-0144116",
        "172049-0196000",
        "172049-0196110",
    }
)
KANJI_AMBIGUOUS_TOWN_CODES: frozenset[str] = frozenset({"042021-0093103", "173843-0089134"})


@pytest.mark.parametrize("numeral_style", list(NumeralStyle))
@pytest.mark.parametrize("lot_style", list(LotStyle))
@pytest.mark.parametrize("digit_width", list(DigitWidth))
def test_decode_output_encodes_back(
    codec: AddressCodec, numeral_style: NumeralStyle, lot_style: LotStyle, digit_width: DigitWidth
) -> None:
    address_format = AddressFormat(
        numeral_style=numeral_style, lot_style=lot_style, digit_width=digit_width
    )
    master_rows = (Path(__file__).parent / "fixtures" / "mt_town_sample.csv").read_text(
        encoding="utf-8"
    )
    town_codes = sorted(
        {f"{row.split(',')[0]}-{row.split(',')[1]}" for row in master_rows.splitlines()[1:]}
        - AMBIGUOUS_TOWN_CODES
        - (KANJI_AMBIGUOUS_TOWN_CODES if numeral_style is NumeralStyle.KANJI else frozenset())
    )
    for town_code in town_codes:
        for lot_suffix in ["", "-5", "-12-3", "-123-45"]:
            code = AddressCode.parse(town_code + lot_suffix)
            assert codec.encode(codec.decode(code, address_format)) == code, str(code)
