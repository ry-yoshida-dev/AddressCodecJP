import pytest

from address_codec_jp.normalization import KanjiNumeral


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("一", 1),
        ("十", 10),
        ("十一", 11),
        ("二十三", 23),
        ("百五", 105),
        ("一〇二", 102),
        ("二千二十六", 2026),
    ],
)
def test_to_int(text: str, expected: int) -> None:
    assert KanjiNumeral.to_int(text) == expected


@pytest.mark.parametrize(
    ("value", "expected"), [(1, "一"), (10, "十"), (23, "二十三"), (1205, "千二百五")]
)
def test_from_int(value: int, expected: str) -> None:
    assert KanjiNumeral.from_int(value) == expected


def test_round_trip() -> None:
    assert all(
        KanjiNumeral.to_int(KanjiNumeral.from_int(value)) == value
        for value in [*range(10000), 12345, 100000]
    )


def test_from_int_uses_digits_from_ten_thousand() -> None:
    assert KanjiNumeral.from_int(10000) == "一〇〇〇〇"


@pytest.mark.parametrize(
    "text", ["〇十", "一二十", "十十", "百千", "五七十二", "一十二", "一百", "一千", ""]
)
def test_rejects_invalid_positional(text: str) -> None:
    assert KanjiNumeral.parse(text) is None
    with pytest.raises(ValueError):
        _ = KanjiNumeral.to_int(text)


def test_rejects_non_numeral() -> None:
    with pytest.raises(ValueError):
        _ = KanjiNumeral.to_int("丸")
