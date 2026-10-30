from collections import defaultdict

from address_codec_jp.address import Address, AddressCode, Municipality, Town
from address_codec_jp.text.matching.municipality_name_index import MunicipalityNameIndex
from address_codec_jp.text.matching.name_index import NameIndex
from address_codec_jp.text.matching.town_source import TownSource
from address_codec_jp.text.normalization import TextNormalizer


class NameSearcher:
    """
    Finder of every registered area that bears a name.

    A name is the whole name of a prefecture, municipality, oaza, or koaza, compared
    after folding notation variants (``藤ヶ丘`` finds 藤が丘) and a leading ``大字``/``字``.
    Parts of a name are not searched. A municipality may be written with its prefecture
    or county; the city of a designated city stands for all its wards, and a ward
    written alone for every ward of that name. An oaza or koaza may follow a prefecture
    or municipality that narrows it down (``府中市宮町``). An oaza is found as its
    oaza-level town, or as its chome and koaza when the oaza itself is not registered.

    Parameters
    ----------
    repository : TownSource
        Source of municipalities and towns, such as ``TownRepository``.
    normalizer : TextNormalizer
        Normalizer applied to registry names.
    """

    def __init__(self, repository: TownSource, normalizer: TextNormalizer) -> None:
        self._repository: TownSource = repository
        self._normalizer: TextNormalizer = normalizer
        self._name_index: MunicipalityNameIndex | None = None
        self._town_name_index: dict[str, set[str]] | None = None

    def search(self, normalized_name: str, *, within: AddressCode | None = None) -> list[Address]:
        """
        List the registered areas that bear a name.

        Parameters
        ----------
        normalized_name : str
            Name normalized by ``TextNormalizer.normalize``.
        within : AddressCode | None
            Prefecture, municipality, or town the areas must lie in, or ``None`` to
            search everywhere.

        Returns
        -------
        list[Address]
            Areas ordered by code. Empty when no area bears the name.

        Raises
        ------
        DatasetNotImportedError
            If the repository contains no municipalities.
        """
        folded = self._normalizer.fold(normalized_name)
        addresses = [
            Address(prefecture=municipality.prefecture, municipality=municipality)
            for municipality in self._find_municipalities(folded)
        ]
        prefecture = self._get_name_index().prefectures.get(folded)
        if prefecture is not None:
            addresses.append(Address(prefecture=prefecture))
        towns = self._find_towns(folded, None)
        for length in range(1, len(folded)):
            areas = self._find_areas(folded[:length])
            if areas:
                towns.extend(self._find_towns(folded[length:], areas))
        addresses.extend(Address.for_town(town) for town in towns)
        unique = {
            str(address.code): address
            for address in addresses
            if within is None or within.contains(address.code)
        }
        return [unique[code] for code in sorted(unique)]

    def _find_municipalities(self, folded_text: str) -> frozenset[Municipality]:
        name_index = self._get_name_index()
        return name_index.municipalities.get(folded_text, frozenset()) | name_index.wards.get(
            folded_text, frozenset()
        )

    def _find_areas(self, folded_text: str) -> list[AddressCode]:
        areas = [
            AddressCode(lg_code=municipality.lg_code)
            for municipality in self._find_municipalities(folded_text)
        ]
        prefecture = self._get_name_index().prefectures.get(folded_text)
        if prefecture is not None:
            areas.append(AddressCode.for_prefecture(prefecture.code))
        return areas

    def _find_towns(self, folded_text: str, areas: list[AddressCode] | None) -> list[Town]:
        key = self._town_key(folded_text)
        names = self._get_town_name_index().get(key)
        if not key or names is None:
            return []
        towns = [
            town
            for town in self._repository.list_towns_named(names)
            if areas is None
            or any(area.contains(AddressCode(lg_code=town.lg_code)) for area in areas)
        ]
        koaza = [town for town in towns if key in self._town_keys(town.koaza_name)]
        oaza_groups: dict[tuple[str, str], list[Town]] = defaultdict(list)
        for town in towns:
            if key in self._town_keys(town.oaza_name):
                oaza_groups[(town.lg_code, town.machiaza_id[:4])].append(town)
        oaza = [
            town
            for group in oaza_groups.values()
            for town in (
                [
                    item
                    for item in group
                    if AddressCode(lg_code=item.lg_code, machiaza_id=item.machiaza_id).is_oaza
                ]
                or group
            )
        ]
        return koaza + oaza

    def _get_name_index(self) -> MunicipalityNameIndex:
        if self._name_index is None:
            self._name_index = MunicipalityNameIndex.build(self._repository, self._normalizer)
        return self._name_index

    def _get_town_name_index(self) -> dict[str, set[str]]:
        if self._town_name_index is None:
            index: dict[str, set[str]] = defaultdict(set)
            for name in self._repository.list_town_names():
                for key in self._town_keys(name):
                    index[key].add(name)
            self._town_name_index = dict(index)
        return self._town_name_index

    def _town_keys(self, name: str) -> set[str]:
        return {
            self._town_key(self._normalizer.fold(normalized))
            for normalized in self._normalizer.normalize_name(name)
        } - {""}

    def _town_key(self, folded_text: str) -> str:
        return self._normalizer.fold(NameIndex.strip_prefix(folded_text))
