from collections import defaultdict
from collections.abc import Mapping
from typing import ClassVar

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
    ``wards``. The index is built from the source on first access, so one instance can
    be shared by every reader of the same source.

    Parameters
    ----------
    repository : TownSource
        Source of the municipalities.
    normalizer : TextNormalizer
        Normalizer applied to the names.
    """

    _PREFECTURE_SUFFIXES: ClassVar[tuple[str, ...]] = ("都", "府", "県")

    def __init__(self, repository: TownSource, normalizer: TextNormalizer) -> None:
        self._repository: TownSource = repository
        self._normalizer: TextNormalizer = normalizer
        self._is_loaded: bool = False
        self._prefectures: dict[str, Prefecture] = {}
        self._municipalities: dict[str, frozenset[Municipality]] = {}
        self._abbreviated_keys: frozenset[str] = frozenset()
        self._wards: dict[str, frozenset[Municipality]] = {}

    @property
    def prefectures(self) -> Mapping[str, Prefecture]:
        """
        Prefectures by key.

        Raises
        ------
        DatasetNotImportedError
            If the source contains no municipalities.
        """
        self._load()
        return self._prefectures

    @property
    def municipalities(self) -> Mapping[str, frozenset[Municipality]]:
        """
        Municipalities by full or abbreviated key.

        Raises
        ------
        DatasetNotImportedError
            If the source contains no municipalities.
        """
        self._load()
        return self._municipalities

    @property
    def abbreviated_keys(self) -> frozenset[str]:
        """
        Keys of ``municipalities`` that omit the ward of a designated city.

        Raises
        ------
        DatasetNotImportedError
            If the source contains no municipalities.
        """
        self._load()
        return self._abbreviated_keys

    @property
    def wards(self) -> Mapping[str, frozenset[Municipality]]:
        """
        Wards of designated cities by the ward name, optionally after the prefecture.

        Raises
        ------
        DatasetNotImportedError
            If the source contains no municipalities.
        """
        self._load()
        return self._wards

    def _load(self) -> None:
        if self._is_loaded:
            return
        municipalities = self._repository.list_municipalities()
        if not municipalities:
            raise DatasetNotImportedError(
                "The town database is empty. Import the town master first."
            )
        prefectures: dict[str, Prefecture] = {}
        full_names: dict[str, set[Municipality]] = defaultdict(set)
        abbreviated_keys: set[str] = set()
        wards: dict[str, set[Municipality]] = defaultdict(set)
        for municipality in municipalities:
            aliases = self._prefecture_aliases(municipality.prefecture_name)
            for alias in aliases:
                prefectures[self._fold(alias)] = municipality.prefecture
            prefixes = {
                prefecture + county
                for prefecture in {"", *aliases}
                for county in {"", municipality.county_name}
            }
            for prefix in prefixes:
                full_key = self._fold(prefix + municipality.city_name + municipality.ward_name)
                full_names[full_key].add(municipality)
                if municipality.ward_name:
                    ward_omitted_key = self._fold(prefix + municipality.city_name)
                    full_names[ward_omitted_key].add(municipality)
                    abbreviated_keys.add(ward_omitted_key)
                    wards[self._fold(prefix + municipality.ward_name)].add(municipality)
        self._prefectures = prefectures
        self._municipalities = {key: frozenset(items) for key, items in full_names.items()}
        self._abbreviated_keys = frozenset(abbreviated_keys)
        self._wards = {key: frozenset(items) for key, items in wards.items()}
        self._is_loaded = True

    def _prefecture_aliases(self, prefecture_name: str) -> set[str]:
        if prefecture_name.endswith(self._PREFECTURE_SUFFIXES):
            return {prefecture_name, prefecture_name[:-1]}
        return {prefecture_name}

    def _fold(self, name: str) -> str:
        return self._normalizer.fold(self._normalizer.normalize(name))
