from collections.abc import Iterator
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from address_codec_jp import (
    AddressCode,
    AddressCodec,
    AddressFormat,
    DigitWidth,
    LotNumber,
    LotStyle,
    NumeralStyle,
    RegistryImporter,
    Town,
)
from address_codec_jp.storage import AbrTownCsvReader

FIXTURE: Path = Path(__file__).parent / "fixtures" / "mt_town_sample.csv"
DOCUMENTED_AMBIGUOUS_TOWNS: frozenset[tuple[str, str]] = frozenset(
    {
        ("042072", "0047000"),
        ("042072", "0009000"),
        ("172049", "0144000"),
        ("172049", "0144116"),
        ("172049", "0196000"),
        ("172049", "0196110"),
        ("173843", "0089000"),
        ("173843", "0089134"),
    }
)
TOWNS: list[Town] = [
    town
    for town in AbrTownCsvReader().read(FIXTURE)
    if (town.lg_code, town.machiaza_id) not in DOCUMENTED_AMBIGUOUS_TOWNS
]
FORMATS: list[AddressFormat] = [
    AddressFormat(numeral_style=numeral_style, lot_style=lot_style, digit_width=digit_width)
    for numeral_style in NumeralStyle
    for lot_style in (LotStyle.RESIDENCE_INDICATION, LotStyle.LAND_PARCEL)
    for digit_width in DigitWidth
]


@pytest.fixture(scope="module")
def shared_codec() -> Iterator[AddressCodec]:
    """Codec shared by the generated examples of this module."""
    with RegistryImporter.open(":memory:") as importer:
        _ = importer.import_town_master(FIXTURE)
        yield AddressCodec(importer.database)


@settings(max_examples=300, deadline=None)
@given(
    town=st.sampled_from(TOWNS),
    block=st.none() | st.integers(min_value=1, max_value=999),
    residence=st.integers(min_value=1, max_value=99),
    address_format=st.sampled_from(FORMATS),
)
def test_decoded_address_encodes_to_the_same_code(
    shared_codec: AddressCodec,
    town: Town,
    block: int | None,
    residence: int,
    address_format: AddressFormat,
) -> None:
    lot = LotNumber() if block is None else LotNumber(block=block, residence=residence)
    code = AddressCode(lg_code=town.lg_code, machiaza_id=town.machiaza_id, lot=lot)
    assert shared_codec.encode(shared_codec.decode(code, address_format)) == code
