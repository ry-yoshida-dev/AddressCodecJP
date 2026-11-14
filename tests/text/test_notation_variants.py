import pytest

from address_codec_jp import AddressCodec


@pytest.mark.parametrize(
    ("address", "expected"),
    [
        ("江戸川区一之江1-2", "131237-0021001-2"),
        ("江戸川区一の江1-2", "131237-0021001-2"),
        ("江戸川区一ノ江1-2", "131237-0021001-2"),
        ("江戸川区一の江町5", "131237-0023000-p5"),
        ("高山市上三の町1", "212032-0063000-p1"),
        ("高山市上三ノ町1", "212032-0063000-p1"),
        ("多賀町一ノ瀬1", "254436-0002000-p1"),
        ("多賀町一之瀬1", "254436-0002000-p1"),
        ("多賀町一の瀬1", "254436-0002000-p1"),
    ],
)
def test_connectives_after_a_numeral_are_interchangeable(
    codec: AddressCodec, address: str, expected: str
) -> None:
    assert str(codec.encode(address)) == expected


@pytest.mark.parametrize(
    "address",
    ["京都市山科区四ノ宮小金塚1", "京都市山科区四の宮小金塚1", "京都市山科区四宮小金塚1"],
)
def test_connective_after_a_numeral_may_be_left_out(codec: AddressCodec, address: str) -> None:
    assert str(codec.encode(address)) == "261106-0182000-p1"


@pytest.mark.parametrize(
    ("address", "expected"),
    [
        ("ニセコ町ニセコ-123", "013951-0013000-p123"),
        ("ニセコ町字ニセコ-123", "013951-0013000-p123"),
        ("ニセコ町字ニセコ－１２３", "013951-0013000-p123"),
        ("山形市流通センタ-1丁目12番3号", "062014-0389001-p12-3"),
    ],
)
def test_dash_before_a_number_after_katakana_separates_it(
    codec: AddressCodec, address: str, expected: str
) -> None:
    assert str(codec.encode(address)) == expected


@pytest.mark.parametrize(
    ("address", "expected_code", "expected_remainder"),
    [
        ("千代田区丸の内1丁目1番 一番ビル", "131016-0011001-1", "一番ビル"),
        ("千代田区丸の内1-1-1 二丁目ビル", "131016-0011001-1-1", "二丁目ビル"),
        ("千代田区丸の内一丁目一番一号 二丁目ビル", "131016-0011001-1-1", "二丁目ビル"),
        ("千代田区丸の内1 一番館", "131016-0011001", "一番館"),
        ("千代田区丸の内1-1 1", "131016-0011001-1-1", ""),
    ],
)
def test_kanji_numeral_after_a_space_starts_the_remainder(
    codec: AddressCodec, address: str, expected_code: str, expected_remainder: str
) -> None:
    address_match = codec.match(address)
    assert str(address_match.code) == expected_code
    assert address_match.remainder == expected_remainder
