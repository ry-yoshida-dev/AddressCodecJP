from collections.abc import Collection

from address_codec_jp.address import Municipality, Town
from address_codec_jp.datasets.address_base_registry import AbrTownCsvReader
from address_codec_jp.text.matching import AreaMatcher, TownSource
from address_codec_jp.text.normalization import LotNumberParser, TextNormalizer
from tests.fixture_paths import TOWN_MASTER


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

    def map_oaza_names(self) -> dict[str, set[str]]:
        """Map the oaza names of the towns to their municipalities."""
        lg_codes_by_name: dict[str, set[str]] = {}
        for town in self._towns:
            if town.oaza_name:
                lg_codes_by_name.setdefault(town.oaza_name, set()).add(town.lg_code)
        return lg_codes_by_name

    def list_street_municipality_codes(self) -> set[str]:
        """List the municipalities that have a street direction."""
        return {town.lg_code for town in self._towns if town.is_street_direction}

    def list_town_names(self) -> set[str]:
        """List the oaza and koaza names of the towns."""
        return {name for town in self._towns for name in (town.oaza_name, town.koaza_name) if name}

    def list_towns_named(self, names: Collection[str]) -> list[Town]:
        """List the towns whose oaza or koaza name is one of the names."""
        return sorted(
            (town for town in self._towns if town.oaza_name in names or town.koaza_name in names),
            key=lambda town: (town.lg_code, town.machiaza_id),
        )


def test_matcher_runs_on_any_town_source() -> None:
    source: TownSource = InMemoryTownSource(list(AbrTownCsvReader().read(TOWN_MASTER)))
    normalizer = TextNormalizer()
    matcher = AreaMatcher(source, normalizer, LotNumberParser())
    address_match = matcher.match(normalizer.normalize("千代田区丸の内1-2-3"), None)
    assert str(address_match.code) == "131016-0011001-2-3"
