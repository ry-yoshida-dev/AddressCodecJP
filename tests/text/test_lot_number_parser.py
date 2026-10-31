import pytest

from address_codec_jp import LotNumber
from address_codec_jp.text.normalization import LotNumberParser


@pytest.mark.parametrize(
    ("text", "lot", "remainder"),
    [
        ("2番3号", LotNumber(2, 3), ""),
        ("2-3", LotNumber(2, 3), ""),
        ("123番地の4", LotNumber(123, 4), ""),
        ("123番地4", LotNumber(123, 4), ""),
        ("2の3", LotNumber(2, 3), ""),
        ("5", LotNumber(5), ""),
        ("2番", LotNumber(2), ""),
        ("2-3-405", LotNumber(2, 3), "405"),
        ("10-1六本木ヒルズ", LotNumber(10, 1), "六本木ヒルズ"),
        ("", LotNumber(), ""),
        ("0", LotNumber(), "0"),
        ("-12-3", LotNumber(12, 3), ""),
        ("12-0", LotNumber(12), "0"),
        ("12丁目", LotNumber(), "12丁目"),
        ("1丁目", LotNumber(), "1丁目"),
        ("5番地3階", LotNumber(5), "3階"),
        ("5番2F", LotNumber(5), "2F"),
        ("5-2F", LotNumber(5), "2F"),
        ("7番地2号館", LotNumber(7), "2号館"),
        ("5番地1番館", LotNumber(5), "1番館"),
        ("2-3号室", LotNumber(2), "3号室"),
        ("5-1-101号室", LotNumber(5, 1), "101号室"),
        ("3階", LotNumber(), "3階"),
        ("2-3Fujiビル", LotNumber(2, 3), "Fujiビル"),
    ],
)
def test_parse(text: str, lot: LotNumber, remainder: str) -> None:
    result = LotNumberParser().parse(text)
    assert result.lot == lot
    assert result.remainder == remainder


@pytest.mark.parametrize(
    ("text", "is_building_number"),
    [
        ("3階", True),
        ("2F", True),
        ("2号館ビル", True),
        ("101号室", True),
        ("3", False),
        ("ビル2F", False),
    ],
)
def test_is_building_number(text: str, is_building_number: bool) -> None:
    assert LotNumberParser().is_building_number(text) is is_building_number
