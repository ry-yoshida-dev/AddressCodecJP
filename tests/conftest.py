from collections.abc import Iterator
from pathlib import Path

import pytest

from address_codec_jp import AddressCodec

FIXTURE_DIRECTORY: Path = Path(__file__).parent / "fixtures"
POSITION_FIXTURES: list[Path] = sorted((FIXTURE_DIRECTORY / "positions").glob("*.csv"))


@pytest.fixture
def codec() -> Iterator[AddressCodec]:
    """Codec backed by an in-memory database loaded with the sample town master."""
    with AddressCodec.create(":memory:") as address_codec:
        _ = address_codec.import_town_master(FIXTURE_DIRECTORY / "mt_town_sample.csv")
        yield address_codec


@pytest.fixture
def located_codec(codec: AddressCodec) -> AddressCodec:
    """Codec whose database also holds the sample position datasets."""
    for path in POSITION_FIXTURES:
        _ = codec.import_positions(path)
    return codec
