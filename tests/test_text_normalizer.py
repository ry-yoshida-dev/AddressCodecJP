import pytest

from address_codec_jp.text.normalization import TextNormalizer


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("丸の内１丁目２番３号", "丸の内1丁目2番3号"),
        ("丸の内一丁目二番三号", "丸の内1丁目2番3号"),
        ("丸の内 1－2－3", "丸の内1-2-3"),
        ("丸の内1ー2ー3", "丸の内1-2-3"),
        ("丸の内1‐2−3", "丸の内1-2-3"),
        ("丸の内1一2", "丸の内1-2"),
        ("丸の内三ー五", "丸の内3-5"),
        ("丸の内1--2", "丸の内1-2"),
        ("〒100-0005 丸の内", "丸の内"),
        ("〒100‐0005 丸の内", "丸の内"),
        ("〒１００ー０００５丸の内", "丸の内"),
        ("流通センタ－", "流通センター"),
        ("流通センタ-1丁目", "流通センター1丁目"),
        ("六本木", "六本木"),
        ("北一条西", "北1条西"),
        ("センター", "センター"),
        ("霞ヶ関", "霞ヶ関"),
        ("字山ノ上", "字山ノ上"),
        ("三ノ輪", "3ノ輪"),
        ("城見の一", "城見の1"),
        ("城見の一12番", "城見の一12番"),
        ("12番地三", "12番地3"),
        ("大曲五", "大曲5"),
        ("九ノ一十二番", "9ノ一12番"),
        ("城見の一十二-三", "城見の一12-3"),
        ("一千二百番", "一1200番"),
        ("2の三", "2の3"),
        ("本市１ 12番", "本市1-12番"),
        ("丸の内 1-2", "丸の内1-2"),
    ],
)
def test_normalize(text: str, expected: str) -> None:
    assert TextNormalizer().normalize(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("霞ヶ関", "霞ケ関"),
        ("霞が関", "霞ケ関"),
        ("丸ノ内", "丸の内"),
        ("3ノ輪", "3の輪"),
        ("2ノ3", "2の3"),
        ("澤", "沢"),
    ],
)
def test_fold(text: str, expected: str) -> None:
    normalizer = TextNormalizer()
    folded = normalizer.fold(normalizer.normalize(text))
    assert folded == expected
    assert len(folded) == len(normalizer.normalize(text))


def test_normalize_name_returns_both_trailing_forms() -> None:
    assert TextNormalizer().normalize_name("白旗九ノ一") == {"白旗9ノ1", "白旗9ノ一"}
    assert TextNormalizer().normalize_name("丸の内") == {"丸の内"}
