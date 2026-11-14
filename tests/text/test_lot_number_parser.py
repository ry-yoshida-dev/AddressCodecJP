import pytest

from address_codec_jp import LotSystem
from address_codec_jp.text.normalization import LotNumberParser


@pytest.mark.parametrize(
    ("text", "numbers", "remainder"),
    [
        ("2番3号", [2, 3], ""),
        ("2-3", [2, 3], ""),
        ("123番地の4", [123, 4], ""),
        ("123番地4", [123, 4], ""),
        ("2の3", [2, 3], ""),
        ("5", [5], ""),
        ("2番", [2], ""),
        ("2-3-405", [2, 3], "405"),
        ("10-1六本木ヒルズ", [10, 1], "六本木ヒルズ"),
        ("の16", [16], ""),
        ("字148-1", [148, 1], ""),
        ("の内", [], "の内"),
        ("", [], ""),
        ("0", [], "0"),
        ("-12-3", [12, 3], ""),
        ("12-0", [12], "0"),
        ("12丁目", [], "12丁目"),
        ("1丁目", [], "1丁目"),
        ("5番地3階", [5], "3階"),
        ("5番2F", [5], "2F"),
        ("5-2F", [5], "2F"),
        ("7番地2号館", [7], "2号館"),
        ("5番地1番館", [5], "1番館"),
        ("2-3号室", [2], "3号室"),
        ("5-1-101号室", [5, 1], "101号室"),
        ("3階", [], "3階"),
        ("2-3Fujiビル", [2, 3], "Fujiビル"),
    ],
)
def test_parse(text: str, numbers: list[int], remainder: str) -> None:
    result = LotNumberParser().parse(text)
    assert result.lot.numbers == numbers
    assert result.remainder == remainder


@pytest.mark.parametrize(
    ("text", "numbers", "notation", "remainder"),
    [
        ("124番地1の1", [124, 1, 1], LotSystem.LAND_PARCEL, ""),
        ("2番3-4号", [2, 3, 4], LotSystem.RESIDENCE_INDICATION, ""),
        ("1番2号の3", [1, 2, 3], LotSystem.RESIDENCE_INDICATION, ""),
        ("2-3の4", [2, 3, 4], None, ""),
        ("2-3-405", [2, 3], None, "405"),
        ("2番3", [2, 3], None, ""),
        ("2番地3", [2, 3], LotSystem.LAND_PARCEL, ""),
        ("2番3号", [2, 3], LotSystem.RESIDENCE_INDICATION, ""),
        ("5-1-101号室", [5, 1], None, "101号室"),
    ],
)
def test_parse_reads_three_numbers_and_the_notation(
    text: str, numbers: list[int], notation: LotSystem | None, remainder: str
) -> None:
    result = LotNumberParser().parse(text)
    assert result.lot.numbers == numbers
    assert result.notation is notation
    assert result.lot.system is (notation or LotSystem.RESIDENCE_INDICATION)
    assert result.remainder == remainder


@pytest.mark.parametrize(
    ("text", "expected"),
    [("405", (405, "")), ("-4ビル", (4, "ビル")), ("3階", None), ("ビル", None)],
)
def test_parse_hyphenated_number(text: str, expected: tuple[int, str] | None) -> None:
    assert LotNumberParser().parse_hyphenated_number(text) == expected


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
