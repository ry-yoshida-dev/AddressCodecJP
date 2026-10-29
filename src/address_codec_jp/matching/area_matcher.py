import re
from collections import defaultdict
from collections.abc import Container
from dataclasses import replace
from typing import ClassVar

from address_codec_jp.domain.address import Address
from address_codec_jp.domain.address_code import AddressCode
from address_codec_jp.domain.address_match import AddressMatch
from address_codec_jp.domain.municipality import Municipality
from address_codec_jp.domain.prefecture import Prefecture
from address_codec_jp.domain.town import Town
from address_codec_jp.errors.address_not_found_error import AddressNotFoundError
from address_codec_jp.errors.ambiguous_address_error import AmbiguousAddressError
from address_codec_jp.errors.dataset_not_imported_error import DatasetNotImportedError
from address_codec_jp.matching.candidate_set import CandidateSet
from address_codec_jp.matching.municipality_match import MunicipalityMatch
from address_codec_jp.matching.name_index import NameIndex
from address_codec_jp.matching.town_interpretation import TownInterpretation
from address_codec_jp.matching.town_source import TownSource
from address_codec_jp.normalization.lot_number_parser import LotNumberParser
from address_codec_jp.normalization.text_normalizer import TextNormalizer

type MatchOutcome = AddressMatch | AddressNotFoundError | AmbiguousAddressError


class AreaMatcher:
    """
    Matcher from a normalized address to the most specific registered area.

    The prefecture or municipality is found by longest prefix. When no town of the
    longest municipality matches the rest, shorter municipality names are tried, and a
    town name must then confirm the municipality. Prefecture and county
    names may be omitted, the prefecture may be written without ``都``/``府``/``県``
    (``東京``), and the ward of a designated city may be omitted (``横浜市山下町``). When
    such a name fits several municipalities, the town name must decide among them. For
    the text after the municipality, every combination of oaza, chome, koaza, and lot
    numbers is tried, and the best ``TownInterpretation`` wins. A reading is discarded when it reads
    no lot numbers but leaves digits unread (``浅草`` + ``橋6-1-1``), or puts lot numbers
    on an oaza-level town that the registry divides into chome. When the best readings
    point to different towns or lot numbers, the address is rejected as ambiguous instead
    of picking one. A postal code given with the address decides only between such
    equally ranked readings, and between municipalities that share a name.

    Parameters
    ----------
    repository : TownSource
        Source of municipalities and towns, such as ``TownRepository``.
    normalizer : TextNormalizer
        Normalizer applied to registry names.
    lot_parser : LotNumberParser
        Parser for the numbers after the town name.
    """

    _CHOME: ClassVar[re.Pattern[str]] = re.compile(
        r"-?(?P<number>[0-9]+)(?P<marker>丁目|丁|-|の|ノ)?"
    )
    _EXPLICIT_CHOME_MARKERS: ClassVar[frozenset[str]] = frozenset({"丁目", "丁"})
    _SEPARATOR_MARKERS: ClassVar[frozenset[str]] = frozenset({"-", "の", "ノ"})
    _UNREAD_CHOME: ClassVar[re.Pattern[str]] = re.compile(r"[0-9]+丁")
    _ASCII_DIGITS: ClassVar[frozenset[str]] = frozenset("0123456789")
    _PREFECTURE_SUFFIXES: ClassVar[tuple[str, ...]] = ("都", "府", "県")

    def __init__(
        self, repository: TownSource, normalizer: TextNormalizer, lot_parser: LotNumberParser
    ) -> None:
        self._repository: TownSource = repository
        self._normalizer: TextNormalizer = normalizer
        self._lot_parser: LotNumberParser = lot_parser
        self._prefecture_index: dict[str, Prefecture] | None = None
        self._municipality_index: dict[str, set[Municipality]] | None = None
        self._ward_omitted_keys: set[str] = set()
        self._oaza_indexes: dict[str, NameIndex] = {}
        self._koaza_indexes: dict[tuple[tuple[str, str], ...], NameIndex] = {}

    def match(self, normalized_address: str, postal_code: str | None) -> AddressMatch:
        """
        Identify the most specific area at the start of a normalized address.

        Parameters
        ----------
        normalized_address : str
            Address normalized by ``TextNormalizer.normalize``.
        postal_code : str | None
            Seven-digit postal code written with the address, or ``None``.

        Returns
        -------
        AddressMatch
            Matched prefecture, municipality, town, lot numbers, and unconsumed text.

        Raises
        ------
        AddressNotFoundError
            If nothing matches.
        AmbiguousAddressError
            If the address fits several areas or lot numbers equally well.
        DatasetNotImportedError
            If the repository contains no towns.
        """
        outcome = self._resolve(normalized_address, postal_code)
        if isinstance(outcome, AddressMatch):
            return outcome
        raise outcome

    def find(self, normalized_address: str, postal_code: str | None) -> AddressMatch | None:
        """
        Identify the area of a normalized address when exactly one fits.

        Parameters
        ----------
        normalized_address : str
            Address normalized by ``TextNormalizer.normalize``.
        postal_code : str | None
            Seven-digit postal code written with the address, or ``None``.

        Returns
        -------
        AddressMatch | None
            Match as returned by ``match``, or ``None`` when nothing matches or the
            address is ambiguous.

        Raises
        ------
        DatasetNotImportedError
            If the repository contains no towns.
        """
        outcome = self._resolve(normalized_address, postal_code)
        return outcome if isinstance(outcome, AddressMatch) else None

    def _resolve(self, normalized_address: str, postal_code: str | None) -> MatchOutcome:
        municipality_matches = [
            self._narrow_by_postal_code(municipality_match, postal_code)
            for municipality_match in self._match_municipalities(normalized_address)
        ]
        if not municipality_matches:
            return self._match_prefecture_only(normalized_address, postal_code)
        longest_match = municipality_matches[0]
        if not NameIndex.strip_prefix(longest_match.remainder):
            return self._match_municipality_only(normalized_address, postal_code, longest_match)
        for municipality_match in municipality_matches:
            is_town_required = (
                municipality_match.is_town_required or municipality_match is not longest_match
            )
            interpretations = self._interpret_town(
                municipality_match, is_town_required=is_town_required
            )
            if interpretations:
                return self._select(
                    normalized_address, postal_code, municipality_match, interpretations
                )
        return AddressNotFoundError(
            f"No town in {self._describe_all(longest_match.municipalities)} matches "
            + f"{longest_match.remainder!r}."
        )

    def _match_prefecture_only(self, text: str, postal_code: str | None) -> MatchOutcome:
        index = self._get_prefecture_index()
        keys = self._matching_prefixes(self._normalizer.fold(text), index)
        if not keys:
            return AddressNotFoundError(f"No prefecture or municipality matches {text!r}.")
        key = keys[0]
        prefecture = index[key]
        remainder = text[len(key) :]
        if remainder:
            return AddressNotFoundError(
                f"No municipality in {prefecture.name} matches {remainder!r}."
            )
        return AddressMatch(
            address=Address(prefecture=prefecture),
            remainder="",
            normalized_address=text,
            postal_code=postal_code,
            town_name_tier=None,
        )

    def _match_municipalities(self, text: str) -> list[MunicipalityMatch]:
        index = self._get_municipality_index()
        return [
            MunicipalityMatch(
                name=text[: len(key)],
                municipalities=sorted(index[key], key=lambda municipality: municipality.lg_code),
                remainder=text[len(key) :],
                is_ward_omitted=key in self._ward_omitted_keys,
            )
            for key in self._matching_prefixes(self._normalizer.fold(text), index)
        ]

    def _narrow_by_postal_code(
        self, municipality_match: MunicipalityMatch, postal_code: str | None
    ) -> MunicipalityMatch:
        if postal_code is None or not municipality_match.is_town_required:
            return municipality_match
        lg_codes = self._repository.list_municipality_codes(postal_code)
        selected = [
            municipality
            for municipality in municipality_match.municipalities
            if municipality.lg_code in lg_codes
        ]
        if not selected:
            return municipality_match
        return replace(
            municipality_match,
            municipalities=selected,
            is_ward_omitted=municipality_match.is_ward_omitted and len(selected) > 1,
        )

    def _match_municipality_only(
        self,
        normalized_address: str,
        postal_code: str | None,
        municipality_match: MunicipalityMatch,
    ) -> MatchOutcome:
        if municipality_match.is_town_required:
            return AmbiguousAddressError(
                f"Municipality {municipality_match.name!r} is ambiguous: "
                + f"{self._describe_all(municipality_match.municipalities)}. "
                + "Add the prefecture or ward.",
                tuple(
                    AddressCode(lg_code=municipality.lg_code)
                    for municipality in municipality_match.municipalities
                ),
            )
        municipality = municipality_match.municipalities[0]
        return AddressMatch(
            address=Address(prefecture=municipality.prefecture, municipality=municipality),
            remainder="",
            normalized_address=normalized_address,
            postal_code=postal_code,
            town_name_tier=None,
        )

    def _interpret_town(
        self, municipality_match: MunicipalityMatch, *, is_town_required: bool
    ) -> list[TownInterpretation]:
        return [
            interpretation
            for municipality in municipality_match.municipalities
            for interpretation in self._interpret_all(municipality, municipality_match.remainder)
            if not is_town_required or interpretation.name_length > 0
        ]

    def _select(
        self,
        normalized_address: str,
        postal_code: str | None,
        municipality_match: MunicipalityMatch,
        interpretations: list[TownInterpretation],
    ) -> MatchOutcome:
        text = municipality_match.remainder
        description = self._describe_all(municipality_match.municipalities)
        best_key = min(interpretation.ranking_key for interpretation in interpretations)
        best = [item for item in interpretations if item.ranking_key == best_key]
        if postal_code is not None:
            best = self._prefer_postal_code(best, postal_code)
        towns = {(town.lg_code, town.machiaza_id): town for item in best for town in item.towns}
        lots = {item.lot for item in best}
        candidates = self._candidate_codes(best)
        if len(towns) == 1 and len(lots) > 1:
            return AmbiguousAddressError(
                f"Lot numbers of {text!r} in {description} are ambiguous: "
                + f"{sorted(map(str, lots))}.",
                candidates,
            )
        if len(towns) > 1:
            names = sorted(
                f"{self._describe(town.municipality)}{town.oaza_name}{town.chome_name}"
                + f"{town.koaza_name}({town.lg_code}-{town.machiaza_id})"
                for town in towns.values()
            )
            return AmbiguousAddressError(
                f"{text!r} in {description} is ambiguous: {names}.", candidates
            )
        town = next(iter(towns.values()))
        return AddressMatch(
            address=Address.for_town(town, best[0].lot),
            remainder=best[0].remainder,
            normalized_address=normalized_address,
            postal_code=postal_code,
            town_name_tier=best[0].loosest_tier,
        )

    def _candidate_codes(
        self, interpretations: list[TownInterpretation]
    ) -> tuple[AddressCode, ...]:
        codes = {
            AddressCode(lg_code=town.lg_code, machiaza_id=town.machiaza_id, lot=item.lot)
            for item in interpretations
            for town in item.towns
        }
        return tuple(sorted(codes, key=str))

    def _prefer_postal_code(
        self, interpretations: list[TownInterpretation], postal_code: str
    ) -> list[TownInterpretation]:
        narrowed = [
            replace(
                interpretation,
                towns=[town for town in interpretation.towns if postal_code in town.postal_codes],
            )
            for interpretation in interpretations
        ]
        return [item for item in narrowed if item.towns] or interpretations

    def _interpret_all(self, municipality: Municipality, text: str) -> list[TownInterpretation]:
        return [
            interpretation
            for oaza_candidates in self._get_oaza_index(municipality.lg_code).match_all(text)
            for chome_candidates in self._chome_options(oaza_candidates)
            for town_candidates in self._koaza_options(chome_candidates)
            if (interpretation := self._interpret(town_candidates, len(text))) is not None
        ]

    def _chome_options(self, candidates: CandidateSet) -> list[CandidateSet]:
        options: list[CandidateSet] = []
        matched = self._CHOME.match(candidates.remainder)
        if matched is not None:
            marker = matched.group("marker")
            is_chome_like = (
                marker in self._EXPLICIT_CHOME_MARKERS
                or marker in self._SEPARATOR_MARKERS
                or matched.end() == len(candidates.remainder)
            )
            number = int(matched.group("number"))
            selected = [town for town in candidates.towns if town.chome_number == number]
            if is_chome_like and selected:
                options.append(
                    CandidateSet(
                        towns=selected,
                        remainder=candidates.remainder[matched.end() :],
                        penalty=candidates.penalty,
                        loosest_tier=candidates.loosest_tier,
                        split_digit_count=candidates.split_digit_count,
                    )
                )
        without_chome = [town for town in candidates.towns if town.chome_number is None]
        if without_chome:
            options.append(
                CandidateSet(
                    towns=without_chome,
                    remainder=candidates.remainder,
                    penalty=candidates.penalty,
                    loosest_tier=candidates.loosest_tier,
                    split_digit_count=candidates.split_digit_count,
                )
            )
        return options

    def _koaza_options(self, candidates: CandidateSet) -> list[CandidateSet]:
        koaza_index = self._get_koaza_index(candidates.towns)
        options = [
            CandidateSet(
                towns=koaza_candidates.towns,
                remainder=koaza_candidates.remainder,
                penalty=candidates.penalty + koaza_candidates.penalty,
                loosest_tier=candidates.loosest_tier.loosen(koaza_candidates.loosest_tier),
                split_digit_count=candidates.split_digit_count + koaza_candidates.split_digit_count,
            )
            for koaza_candidates in koaza_index.match_all(candidates.remainder)
        ]
        without_koaza = [town for town in candidates.towns if not town.koaza_name]
        if without_koaza:
            options.append(
                CandidateSet(
                    towns=without_koaza,
                    remainder=candidates.remainder,
                    penalty=candidates.penalty,
                    loosest_tier=candidates.loosest_tier,
                    split_digit_count=candidates.split_digit_count,
                )
            )
        return options

    def _interpret(self, candidates: CandidateSet, text_length: int) -> TownInterpretation | None:
        lot_result = self._lot_parser.parse(candidates.remainder)
        if self._UNREAD_CHOME.match(lot_result.remainder):
            return None
        if not lot_result.lot.numbers and not self._ASCII_DIGITS.isdisjoint(lot_result.remainder):
            return None
        towns = [
            town for town in candidates.towns if town.is_registered or not lot_result.lot.numbers
        ]
        if not towns:
            return None
        return TownInterpretation(
            towns=towns,
            lot=lot_result.lot,
            remainder=lot_result.remainder,
            name_length=text_length - len(candidates.remainder) - candidates.split_digit_count,
            penalty=candidates.penalty,
            loosest_tier=candidates.loosest_tier,
        )

    def _get_prefecture_index(self) -> dict[str, Prefecture]:
        if self._prefecture_index is None:
            self._prefecture_index = {
                self._fold_name(alias): municipality.prefecture
                for municipality in self._repository.list_municipalities()
                for alias in self._prefecture_aliases(municipality.prefecture_name)
            }
        return self._prefecture_index

    def _get_municipality_index(self) -> dict[str, set[Municipality]]:
        if self._municipality_index is None:
            index: dict[str, set[Municipality]] = defaultdict(set)
            municipalities = self._repository.list_municipalities()
            if not municipalities:
                raise DatasetNotImportedError(
                    "The town database is empty. Import the town master first."
                )
            for municipality in municipalities:
                prefixes = {
                    prefecture + county
                    for prefecture in {"", *self._prefecture_aliases(municipality.prefecture_name)}
                    for county in {"", municipality.county_name}
                }
                for prefix in prefixes:
                    full_key = self._fold_name(
                        prefix + municipality.city_name + municipality.ward_name
                    )
                    index[full_key].add(municipality)
                    if municipality.ward_name:
                        ward_omitted_key = self._fold_name(prefix + municipality.city_name)
                        index[ward_omitted_key].add(municipality)
                        self._ward_omitted_keys.add(ward_omitted_key)
            self._municipality_index = dict(index)
        return self._municipality_index

    def _get_oaza_index(self, lg_code: str) -> NameIndex:
        if lg_code not in self._oaza_indexes:
            index = NameIndex(self._normalizer)
            for town in self._repository.list_towns(lg_code):
                index.add(self._oaza_key_name(town), town)
            self._oaza_indexes[lg_code] = index
        return self._oaza_indexes[lg_code]

    def _get_koaza_index(self, towns: list[Town]) -> NameIndex:
        key = tuple((town.lg_code, town.machiaza_id) for town in towns)
        if key not in self._koaza_indexes:
            index = NameIndex(self._normalizer)
            for town in towns:
                if town.koaza_name:
                    index.add(town.koaza_name, town)
            self._koaza_indexes[key] = index
        return self._koaza_indexes[key]

    def _oaza_key_name(self, town: Town) -> str:
        return town.oaza_name + (town.chome_name if town.chome_number is None else "")

    def _prefecture_aliases(self, prefecture_name: str) -> set[str]:
        if prefecture_name.endswith(self._PREFECTURE_SUFFIXES):
            return {prefecture_name, prefecture_name[:-1]}
        return {prefecture_name}

    def _fold_name(self, name: str) -> str:
        return self._normalizer.fold(self._normalizer.normalize(name))

    def _matching_prefixes(self, text: str, keys: Container[str]) -> list[str]:
        return [text[:length] for length in range(len(text), 0, -1) if text[:length] in keys]

    def _describe(self, municipality: Municipality) -> str:
        return municipality.prefecture_name + municipality.city_name + municipality.ward_name

    def _describe_all(self, municipalities: list[Municipality]) -> str:
        return ", ".join(self._describe(municipality) for municipality in municipalities)
