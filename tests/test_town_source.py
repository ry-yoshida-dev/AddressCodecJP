from pathlib import Path

from address_codec_jp.domain import Municipality, Town
from address_codec_jp.matching import AreaMatcher, TownSource
from address_codec_jp.normalization import LotNumberParser, TextNormalizer
from address_codec_jp.registry import AbrTownCsvReader

FIXTURE: Path = Path(__file__).parent / "fixtures" / "mt_town_sample.csv"


class InMemoryTownSource:
    """Town source held in dictionaries, without a database."""

    def __init__(self, towns: list[Town]) -> None:
        self._towns: list[Town] = towns

    def list_municipalities(self) -> list[Municipality]:
        """List the municipalities of the towns."""
        by_code = {town.lg_code: town.municipality for town in self._towns}
        return [by_code[lg_code] for lg_code in sorted(by_code)]

    def list_towns(self, lg_code: str) -> list[Town]:
        """List the towns of a municipality."""
        return sorted(
            (town for town in self._towns if town.lg_code == lg_code),
            key=lambda town: town.machiaza_id,
        )

    def list_municipality_codes(self, postal_code: str) -> set[str]:
        """List the municipalities that have a town with the postal code."""
        return {town.lg_code for town in self._towns if postal_code in town.postal_codes}


def test_matcher_runs_on_any_town_source() -> None:
    source: TownSource = InMemoryTownSource(list(AbrTownCsvReader().read(FIXTURE)))
    normalizer = TextNormalizer()
    matcher = AreaMatcher(source, normalizer, LotNumberParser())
    address_match = matcher.match(normalizer.normalize("千代田区丸の内1-2-3"), None)
    assert str(address_match.code) == "131016-0001001-2-3"
