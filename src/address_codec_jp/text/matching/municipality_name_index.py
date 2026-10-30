from collections import defaultdict
from collections.abc import Mapping
from typing import ClassVar, Self

from address_codec_jp.address import Municipality, Prefecture
from address_codec_jp.errors import DatasetNotImportedError
from address_codec_jp.text.matching.town_source import TownSource
from address_codec_jp.text.normalization import TextNormalizer


class MunicipalityNameIndex:
    """
    Index of the prefecture and municipality names as they may be written.

    Keys are folded normalized names. A prefecture is indexed with and without
    ``都``/``府``/``県`` (``東京``), and a municipality with and without its prefecture and
    county. A ward of a designated city is indexed by its city and ward, by its city
    alone, an abbreviated key shared by all wards of the city, and by its ward alone in
    ``wards``.

    Parameters
    ----------
    prefectures : Mapping[str, Prefecture]
        Prefectures by key.
    municipalities : Mapping[str, frozenset[Municipality]]
        Municipalities by full or abbreviated key.
    abbreviated_keys : frozenset[str]
        Keys of ``municipalities`` that omit the ward of a designated city.
    wards : Mapping[str, frozenset[Municipality]]
        Wards of designated cities by the ward name, optionally after the prefecture.
    """

    _PREFECTURE_SUFFIXES: ClassVar[tuple[str, ...]] = ("都", "府", "県")

    def __init__(
        self,
        prefectures: Mapping[str, Prefecture],
        municipalities: Mapping[str, frozenset[Municipality]],
        abbreviated_keys: frozenset[str],
        wards: Mapping[str, frozenset[Municipality]],
    ) -> None:
        self.prefectures: Mapping[str, Prefecture] = prefectures
        self.municipalities: Mapping[str, frozenset[Municipality]] = municipalities
        self.abbreviated_keys: frozenset[str] = abbreviated_keys
        self.wards: Mapping[str, frozenset[Municipality]] = wards

    @classmethod
    def build(cls, repository: TownSource, normalizer: TextNormalizer) -> Self:
        """
        Index the municipalities of a town source.

        Parameters
        ----------
        repository : TownSource
            Source of the municipalities.
        normalizer : TextNormalizer
            Normalizer applied to the names.

        Returns
        -------
        Self
            Index of every prefecture and municipality of the source.

        Raises
        ------
        DatasetNotImportedError
            If the source contains no municipalities.
        """
        municipalities = repository.list_municipalities()
        if not municipalities:
            raise DatasetNotImportedError(
                "The town database is empty. Import the town master first."
            )
        prefectures: dict[str, Prefecture] = {}
        full_names: dict[str, set[Municipality]] = defaultdict(set)
        abbreviated_keys: set[str] = set()
        wards: dict[str, set[Municipality]] = defaultdict(set)
        for municipality in municipalities:
            aliases = cls._prefecture_aliases(municipality.prefecture_name)
            for alias in aliases:
                prefectures[cls._fold(normalizer, alias)] = municipality.prefecture
            prefixes = {
                prefecture + county
                for prefecture in {"", *aliases}
                for county in {"", municipality.county_name}
            }
            for prefix in prefixes:
                full_key = cls._fold(
                    normalizer, prefix + municipality.city_name + municipality.ward_name
                )
                full_names[full_key].add(municipality)
                if municipality.ward_name:
                    ward_omitted_key = cls._fold(normalizer, prefix + municipality.city_name)
                    full_names[ward_omitted_key].add(municipality)
                    abbreviated_keys.add(ward_omitted_key)
                    wards[cls._fold(normalizer, prefix + municipality.ward_name)].add(municipality)
        return cls(
            prefectures=prefectures,
            municipalities={key: frozenset(items) for key, items in full_names.items()},
            abbreviated_keys=frozenset(abbreviated_keys),
            wards={key: frozenset(items) for key, items in wards.items()},
        )

    @classmethod
    def _prefecture_aliases(cls, prefecture_name: str) -> set[str]:
        if prefecture_name.endswith(cls._PREFECTURE_SUFFIXES):
            return {prefecture_name, prefecture_name[:-1]}
        return {prefecture_name}

    @staticmethod
    def _fold(normalizer: TextNormalizer, name: str) -> str:
        return normalizer.fold(normalizer.normalize(name))
