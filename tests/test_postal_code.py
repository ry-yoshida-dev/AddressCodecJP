import pytest

from address_codec_jp import AddressCodec, AddressFormat, DigitWidth
from address_codec_jp.normalization import TextNormalizer


@pytest.mark.parametrize(
    ("address", "expected"),
    [
        ("〒100-0005 東京都千代田区丸の内", "1000005"),
        ("１００－０００５千代田区", "1000005"),
        ("100 0005 千代田区", "1000005"),
        ("1000005千代田区", "1000005"),
        ("千代田区丸の内1-2-3", None),
        ("〒100-005 千代田区", None),
    ],
)
def test_postal_code_is_extracted(address: str, expected: str | None) -> None:
    assert TextNormalizer().extract_postal_code(address) == expected


@pytest.mark.parametrize(
    ("address", "expected"),
    [
        ("〒183-0023 府中市", "132063"),
        ("〒726-0004 府中市", "342084"),
        ("〒726-0004 府中市府川町1-2", "342084-0001000-1-2"),
        ("〒231-0023 横浜市山下町", "141046-0001000"),
        ("〒981-1224 名取市箱塚12番3号", "042072-0009000-12-3"),
    ],
)
def test_postal_code_decides_between_equal_readings(
    codec: AddressCodec, address: str, expected: str
) -> None:
    address_match = codec.match(address)
    assert str(address_match.code) == expected
    assert address_match.postal_code is not None


@pytest.mark.parametrize("address", ["〒999-9999 府中市", "〒999-9999 名取市箱塚12番3号"])
def test_unknown_postal_code_keeps_the_ambiguity(codec: AddressCodec, address: str) -> None:
    with pytest.raises(LookupError, match="ambiguous"):
        _ = codec.match(address)


def test_postal_code_does_not_override_the_written_town(codec: AddressCodec) -> None:
    assert str(codec.encode("〒100-0013 千代田区丸の内1-2-3")) == "131016-0001001-2-3"


@pytest.mark.parametrize(
    ("code", "address_format", "expected"),
    [
        (
            "131016-0001001-2-3",
            AddressFormat(is_postal_code_included=True),
            "〒100-0005 東京都千代田区丸の内1丁目2番3号",
        ),
        (
            "131016-0001001",
            AddressFormat(is_postal_code_included=True, digit_width=DigitWidth.FULL),
            "〒１００－０００５ 東京都千代田区丸の内１丁目",
        ),
        (
            "131067-0001000",
            AddressFormat(is_postal_code_included=True),
            "〒111-0053 東京都台東区浅草橋",
        ),
        ("042072-0047000", AddressFormat(is_postal_code_included=True), "宮城県名取市箱塚"),
        ("131016", AddressFormat(is_postal_code_included=True), "東京都千代田区"),
    ],
)
def test_decode_writes_the_registered_postal_code(
    codec: AddressCodec, code: str, address_format: AddressFormat, expected: str
) -> None:
    assert codec.decode(code, address_format) == expected


def test_complemented_oaza_takes_the_postal_codes_of_its_chome(codec: AddressCodec) -> None:
    town = codec.match("千代田区丸の内").address.town
    assert town is not None
    assert town.postal_codes == ("1000005",)
    assert not town.is_registered
