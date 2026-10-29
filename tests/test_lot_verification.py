import pytest

from address_codec_jp import AddressCodec


@pytest.mark.parametrize(
    ("address", "expected"),
    [
        ("千代田区丸の内1-2-3", "131016-0011001-2-3"),
        ("千代田区丸の内1-2", "131016-0011001-2"),
        ("千代田区丸の内1丁目", "131016-0011001"),
        ("三芳町竹間沢123-4", "113247-0001000-123-4"),
        ("三芳町竹間沢123", "113247-0001000-123"),
        ("東京都", "130001"),
    ],
)
def test_registered_lots_are_accepted(
    located_codec: AddressCodec, address: str, expected: str
) -> None:
    assert str(located_codec.encode(address, is_lot_verified=True)) == expected


@pytest.mark.parametrize(
    ("address", "message"),
    [
        ("千代田区丸の内1-2-9", "not registered"),
        ("千代田区丸の内1-2-4", "not registered"),
        ("千代田区丸の内1-5", "not registered"),
        ("三芳町竹間沢124", "not registered"),
        ("千代田区丸の内2-1-1", "has been imported"),
    ],
)
def test_unregistered_lots_are_rejected(
    located_codec: AddressCodec, address: str, message: str
) -> None:
    assert located_codec.encode(address).lot.numbers
    with pytest.raises(LookupError, match=message):
        _ = located_codec.encode(address, is_lot_verified=True)


def test_verification_requires_a_lot_master(codec: AddressCodec) -> None:
    with pytest.raises(RuntimeError, match="No block, residence, or parcel master"):
        _ = codec.encode("千代田区丸の内1-2-3", is_lot_verified=True)
