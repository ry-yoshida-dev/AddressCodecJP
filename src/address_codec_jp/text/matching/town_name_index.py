from collections import defaultdict
from collections.abc import Mapping, Set
from typing import ClassVar

from address_codec_jp.address import Municipality, Town
from address_codec_jp.text.matching.name_index import NameIndex
from address_codec_jp.text.matching.town_source import TownSource
from address_codec_jp.text.normalization import TextNormalizer


class TownNameIndex:
    """
    Indexes of the oaza and koaza names of the towns, each built on first use.

    Oaza names are indexed nationwide by their folded key, for addresses without a
    municipality, and per municipality as a ``NameIndex`` of oaza and chome names. Koaza
    names are indexed per group of towns that share an oaza reading, and the
    municipalities with street directions are listed for addresses that start with one.

    Parameters
    ----------
    repository : TownSource
        Source of the municipalities and towns.
    normalizer : TextNormalizer
        Normalizer applied to the names.
    """

    _OAZA_CHOME_PART: ClassVar[str] = "000"

    def __init__(self, repository: TownSource, normalizer: TextNormalizer) -> None:
        self._repository: TownSource = repository
        self._normalizer: TextNormalizer = normalizer
        self._oaza_municipality_codes: dict[str, set[str]] | None = None
        self._municipalities_by_code: dict[str, Municipality] | None = None
        self._street_municipality_codes: frozenset[str] | None = None
        self._oaza_indexes: dict[str, NameIndex] = {}
        self._towns_by_id: dict[str, dict[str, Town]] = {}
        self._koaza_indexes: dict[tuple[tuple[str, str], ...], NameIndex] = {}

    @property
    def oaza_municipality_codes(self) -> Mapping[str, Set[str]]:
        """Local government codes of the municipalities with an oaza, by folded name."""
        if self._oaza_municipality_codes is None:
            index: dict[str, set[str]] = defaultdict(set)
            for oaza_name, lg_codes in self._repository.map_oaza_names().items():
                for normalized_name in self._normalizer.normalize_name(oaza_name):
                    key = self.fold(normalized_name)
                    if key:
                        index[key].update(lg_codes)
            self._oaza_municipality_codes = dict(index)
        return self._oaza_municipality_codes

    @property
    def municipalities_by_code(self) -> Mapping[str, Municipality]:
        """Every municipality of the source by its local government code."""
        if self._municipalities_by_code is None:
            self._municipalities_by_code = {
                municipality.lg_code: municipality
                for municipality in self._repository.list_municipalities()
            }
        return self._municipalities_by_code

    @property
    def street_municipality_codes(self) -> frozenset[str]:
        """Local government codes of the municipalities with a street direction."""
        if self._street_municipality_codes is None:
            self._street_municipality_codes = frozenset(
                self._repository.list_street_municipality_codes()
            )
        return self._street_municipality_codes

    def oazas(self, lg_code: str) -> NameIndex:
        """
        Index the oaza names of a municipality, with the chome of unnumbered chome.

        Parameters
        ----------
        lg_code : str
            Local government code of the municipality.

        Returns
        -------
        NameIndex
            Towns of the municipality by oaza name.
        """
        if lg_code not in self._oaza_indexes:
            index = NameIndex(self._normalizer)
            towns = self._repository.list_towns(lg_code)
            for town in towns:
                index.add(
                    town.oaza_name + (town.chome_name if town.chome_number is None else ""), town
                )
            self._oaza_indexes[lg_code] = index
            self._towns_by_id[lg_code] = {town.machiaza_id: town for town in towns}
        return self._oaza_indexes[lg_code]

    def list_street_directions(self, lg_code: str) -> list[Town]:
        """
        List the towns of a municipality whose koaza is a street direction.

        Parameters
        ----------
        lg_code : str
            Local government code of the municipality.

        Returns
        -------
        list[Town]
            Towns with ``Town.is_street_direction``; empty outside Kyoto.
        """
        _ = self.oazas(lg_code)
        return [town for town in self._towns_by_id[lg_code].values() if town.is_street_direction]

    def find_oaza(self, town: Town) -> Town | None:
        """
        Find the oaza-level town of a chome or koaza.

        Parameters
        ----------
        town : Town
            Town whose oaza is wanted.

        Returns
        -------
        Town | None
            Town with the oaza part of ``town.machiaza_id`` and the chome part ``000``,
            or ``None`` when the registry has no such town.
        """
        _ = self.oazas(town.lg_code)
        return self._towns_by_id[town.lg_code].get(town.machiaza_id[:4] + self._OAZA_CHOME_PART)

    def koazas(self, towns: list[Town]) -> NameIndex:
        """
        Index the koaza names of a group of towns.

        Parameters
        ----------
        towns : list[Town]
            Towns that share an oaza and chome reading.

        Returns
        -------
        NameIndex
            Towns with a koaza, by koaza name.
        """
        key = tuple((town.lg_code, town.machiaza_id) for town in towns)
        if key not in self._koaza_indexes:
            index = NameIndex(self._normalizer)
            for town in towns:
                if town.koaza_name:
                    index.add(town.koaza_name, town)
            self._koaza_indexes[key] = index
        return self._koaza_indexes[key]

    def fold(self, normalized_text: str) -> str:
        """
        Fold a normalized text for comparison with the oaza keys.

        Parameters
        ----------
        normalized_text : str
            Text after the prefecture or municipality.

        Returns
        -------
        str
            Folded text without a leading ``大字`` or ``字``.
        """
        return self._normalizer.fold(NameIndex.strip_prefix(normalized_text))
