from pathlib import Path

import pytest

from address_codec_jp import AddressCode, AddressCodec, RegistryImporter
from tests.fixture_paths import POSITION_FIXTURES


@pytest.mark.parametrize(
    ("address", "expected"),
    [
        ("千代田区丸の内1-2-3", "131016-0011001-2-3"),
        ("千代田区丸の内1-2", "131016-0011001-2"),
        ("千代田区丸の内1丁目", "131016-0011001"),
        ("三芳町竹間沢123-4", "113247-0001000-p123-4"),
        ("三芳町竹間沢123", "113247-0001000-p123"),
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
        ("千代田区丸の内1-2-5", "not registered"),
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


@pytest.mark.parametrize(
    ("address", "expected"),
    [
        ("千代田区丸の内1丁目", "131016-0011001"),
        ("千代田区", "131016"),
        ("東京都", "130001"),
    ],
)
def test_addresses_without_lots_need_no_lot_master(
    codec: AddressCodec, address: str, expected: str
) -> None:
    assert str(codec.encode(address, is_lot_verified=True)) == expected


def test_verification_requires_a_lot_master(codec: AddressCodec) -> None:
    with pytest.raises(RuntimeError, match="No block, residence, or parcel master"):
        _ = codec.encode("千代田区丸の内1-2-3", is_lot_verified=True)


@pytest.mark.parametrize(
    ("address", "is_lot_verified", "expected", "remainder"),
    [
        ("三芳町竹間沢124番地1の1", False, "113247-0001000-p124-1-1", ""),
        ("三芳町竹間沢124番地1の1", True, "113247-0001000-p124-1-1", ""),
        ("千代田区丸の内1-2-4-1", False, "131016-0011001-2-4", "1"),
        ("千代田区丸の内1-2-4-1", True, "131016-0011001-2-4-1", ""),
        ("千代田区丸の内1-2-3-405", True, "131016-0011001-2-3", "405"),
        ("千代田区丸の内1丁目2番3-4号", False, "131016-0011001-2-3-4", ""),
    ],
)
def test_third_lot_numbers(
    located_codec: AddressCodec,
    address: str,
    *,
    is_lot_verified: bool,
    expected: str,
    remainder: str,
) -> None:
    address_match = located_codec.match(address, is_lot_verified=is_lot_verified)
    assert str(address_match.code) == expected
    assert address_match.remainder == remainder


def test_verification_falls_back_to_the_other_numbering_system(
    importer: RegistryImporter, tmp_path: Path
) -> None:
    for path in POSITION_FIXTURES:
        _ = importer.import_file(path)
    parcels = tmp_path / "mt_parcel_extra.csv"
    _ = parcels.write_text(
        "lg_code,machiaza_id,prc_id,prc_num1,prc_num2,prc_num3,ablt_date\n"
        + "131016,0011001,000070000100000,7,1,,\n",
        encoding="utf-8",
    )
    _ = importer.import_file(parcels)
    codec = AddressCodec(importer.database)
    assert str(codec.encode("千代田区丸の内1-7-1")) == "131016-0011001-7-1"
    verified = codec.encode("千代田区丸の内1-7-1", is_lot_verified=True)
    assert str(verified) == "131016-0011001-p7-1"
    residence = codec.encode("千代田区丸の内1-2-3", is_lot_verified=True)
    assert str(residence) == "131016-0011001-2-3"
    with pytest.raises(LookupError, match="not registered"):
        codec.verify_lot(AddressCode.parse("131016-0011001-7-1"))


def test_land_parcel_codes_are_located_as_parcels(located_codec: AddressCodec) -> None:
    parcel = located_codec.locate_code("131016-0011001-p2-3")
    residence = located_codec.locate_code("131016-0011001-2-3")
    assert parcel.is_exact
    assert residence.is_exact
    assert parcel.coordinate != residence.coordinate
    assert located_codec.has_parcel_shape("131016-0011001-p2-3")
    assert not located_codec.has_parcel_shape("131016-0011001-2-3")
