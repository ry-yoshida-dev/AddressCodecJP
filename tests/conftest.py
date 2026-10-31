from collections.abc import Iterator
from pathlib import Path

import pytest

from address_codec_jp import AddressCodec, RegistryImporter
from tests.fixture_paths import FIXTURE_DIRECTORY

POSITION_FIXTURES: list[Path] = sorted((FIXTURE_DIRECTORY / "positions").glob("*.csv"))


@pytest.fixture
def importer() -> Iterator[RegistryImporter]:
    """Provide an importer on an in-memory database loaded with the sample town master."""
    with RegistryImporter.open(":memory:") as registry_importer:
        _ = registry_importer.import_file(FIXTURE_DIRECTORY / "mt_town_sample.csv")
        yield registry_importer


@pytest.fixture
def codec(importer: RegistryImporter) -> AddressCodec:
    """Provide a codec on the database of ``importer``."""
    return AddressCodec(importer.database)


@pytest.fixture
def located_codec(importer: RegistryImporter) -> AddressCodec:
    """Provide a codec whose database also holds the sample position datasets."""
    for path in POSITION_FIXTURES:
        _ = importer.import_file(path)
    return AddressCodec(importer.database)
