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
