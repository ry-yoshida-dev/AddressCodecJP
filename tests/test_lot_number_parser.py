import pytest

from address_codec_jp import LotNumber
from address_codec_jp.normalization import LotNumberParser


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
    ],
)
def test_parse(text: str, lot: LotNumber, remainder: str) -> None:
    result = LotNumberParser().parse(text)
    assert result.lot == lot
    assert result.remainder == remainder
