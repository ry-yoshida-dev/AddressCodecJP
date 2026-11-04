from collections.abc import Iterator

import pytest

from address_codec_jp import AddressCode, RegistryImporter
from address_codec_jp.database.importing.census_area_matcher import CensusAreaMatcher
from address_codec_jp.datasets.boundaries import CensusArea
from address_codec_jp.geometry import AreaShape, Polygon
from address_codec_jp.text.matching import AreaMatcher
from address_codec_jp.text.normalization import LotNumberParser, TextNormalizer
from tests.fixture_paths import FIXTURE_DIRECTORY

SQUARE: AreaShape = AreaShape(
    (Polygon(((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0), (0.0, 0.0))),)
)


@pytest.fixture
def matcher() -> Iterator[CensusAreaMatcher]:
    """Provide a matcher over towns that the census names differently."""
    with RegistryImporter.open(":memory:") as importer:
        _ = importer.import_file(FIXTURE_DIRECTORY / "mt_town_census_names.csv")
        towns = importer.database.towns
        normalizer = TextNormalizer()
        yield CensusAreaMatcher(
            towns, normalizer, AreaMatcher(towns, normalizer, LotNumberParser())
        )


def _area(municipality: str, town_name: str) -> CensusArea:
    return CensusArea(
        key_code="0",
        address=municipality + town_name,
        town_name=town_name,
        shape=SQUARE,
        is_land=True,
    )


@pytest.mark.parametrize(
    ("municipality", "town_name", "lg_code", "expected"),
    [
        ("滋賀県彦根市", "大薮町", "252026", "252026-0012000"),
        ("東京都千代田区", "神田三崎町一丁目", "131016", "131016-0049001"),
        ("東京都千代田区", "三崎町一丁目", "131016", "131016-0049001"),
        ("滋賀県甲賀市", "泉", "252093", "252093-0090000"),
        ("滋賀県甲賀市", "北脇", "252093", "252093-0102000"),
        ("東京都調布市", "下布田", "132080", "132080-0002000"),
    ],
)
def test_census_names_are_matched_to_registered_towns(
    matcher: CensusAreaMatcher, municipality: str, town_name: str, lg_code: str, expected: str
) -> None:
    assert matcher.match(_area(municipality, town_name), lg_code) == AddressCode.parse(expected)


@pytest.mark.parametrize(
    ("municipality", "town_name", "lg_code"),
    [
        ("滋賀県甲賀市", "内貴", "25"),
        ("滋賀県甲賀市", "市場", "252093"),
        ("東京都千代田区", "錦", "131016"),
    ],
)
def test_census_names_without_a_single_town_are_skipped(
    matcher: CensusAreaMatcher, municipality: str, town_name: str, lg_code: str
) -> None:
    assert matcher.match(_area(municipality, town_name), lg_code) is None


def test_address_must_end_with_the_town_name(matcher: CensusAreaMatcher) -> None:
    area = CensusArea(
        key_code="0", address="滋賀県彦根市", town_name="大薮町", shape=SQUARE, is_land=True
    )
    with pytest.raises(ValueError, match="does not end with"):
        _ = matcher.match(area, "252026")
