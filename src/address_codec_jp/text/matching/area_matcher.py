import re
from collections import defaultdict
from collections.abc import Container
from dataclasses import replace
from typing import ClassVar

from address_codec_jp.address import Address, AddressCode, Municipality, Prefecture, Town
from address_codec_jp.errors import (
    AddressNotFoundError,
    AmbiguousAddressError,
)
from address_codec_jp.results import AddressMatch
from address_codec_jp.text.matching.candidate_set import CandidateSet
from address_codec_jp.text.matching.municipality_match import MunicipalityMatch
from address_codec_jp.text.matching.municipality_name_index import MunicipalityNameIndex
from address_codec_jp.text.matching.name_index import NameIndex
from address_codec_jp.text.matching.town_interpretation import TownInterpretation
from address_codec_jp.text.matching.town_source import TownSource
from address_codec_jp.text.normalization import LotNumberParser, TextNormalizer

type MatchOutcome = AddressMatch | AddressNotFoundError | AmbiguousAddressError


class AreaMatcher:
    """
    Matcher from a normalized address to the most specific registered area.

    The prefecture or municipality is found by longest prefix. When no town of the
    longest municipality matches the rest, shorter municipality names are tried, and a
    town name must then confirm the municipality. Prefecture and county
    names may be omitted, the prefecture may be written without ``都``/``府``/``県``
    (``東京``), and the ward of a designated city may be omitted (``横浜市山下町``). When
    such a name fits several municipalities, the town name must decide among them. A ward
    written without its city (``中京区``) is tried only after every full municipality name.
    An address that starts with no municipality name is read as a town name, optionally
    after the prefecture (``霞が関1-1-1``): every municipality with an oaza that starts the
    text is tried, and the reading must include lot numbers or end with the town name. An
    oaza name followed by a number or the end of the text and found in too many
    municipalities (``本町1-1``) rejects the address as ambiguous. For
    the text after the municipality, every combination of oaza, chome, koaza, and lot
    numbers is tried, and the best ``TownInterpretation`` wins. A reading is discarded when it reads
    no lot numbers but leaves digits unread (``浅草`` + ``橋6-1-1``), or puts lot numbers
    on an oaza-level town that the registry divides into chome. When the best readings
    point to different towns or lot numbers, the address is rejected as ambiguous instead
    of picking one. A postal code given with the address decides only between such
    equally ranked readings, and between municipalities that share a name. An area given
    as ``within`` discards every municipality and town outside it before the readings
    are ranked. A designated city written without its ward still needs a town name when
    the postal code or ``within`` leaves only one of its wards.

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
    _TOWN_ONLY_MUNICIPALITY_LIMIT: ClassVar[int] = 50
    _TOWN_NAME_END: ClassVar[re.Pattern[str]] = re.compile(r"$|[0-9-]")

    def __init__(
        self, repository: TownSource, normalizer: TextNormalizer, lot_parser: LotNumberParser
    ) -> None:
        self._repository: TownSource = repository
        self._normalizer: TextNormalizer = normalizer
        self._lot_parser: LotNumberParser = lot_parser
        self._name_index: MunicipalityNameIndex = MunicipalityNameIndex(repository, normalizer)
        self._oaza_municipality_index: dict[str, set[str]] | None = None
        self._municipalities_by_code: dict[str, Municipality] | None = None
        self._oaza_indexes: dict[str, NameIndex] = {}
        self._koaza_indexes: dict[tuple[tuple[str, str], ...], NameIndex] = {}

    @property
    def municipality_names(self) -> MunicipalityNameIndex:
        """Prefecture and municipality names of the repository, built on first use."""
        return self._name_index

    def match(
        self,
        normalized_address: str,
        postal_code: str | None,
        *,
        within: AddressCode | None = None,
    ) -> AddressMatch:
        """
        Identify the most specific area at the start of a normalized address.

        Parameters
        ----------
        normalized_address : str
            Address normalized by ``TextNormalizer.normalize``.
        postal_code : str | None
            Seven-digit postal code written with the address, or ``None``.
        within : AddressCode | None
            Prefecture, municipality, or town the address must lie in, or ``None`` to
            search everywhere.

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
        outcome = self.interpret(normalized_address, postal_code, within=within)
        if isinstance(outcome, AddressMatch):
            return outcome
        raise outcome

    def interpret(
        self,
        normalized_address: str,
        postal_code: str | None,
        *,
        within: AddressCode | None = None,
    ) -> MatchOutcome:
        """
        Identify the area of a normalized address, returning failures instead of raising.

        Parameters
        ----------
        normalized_address : str
            Address normalized by ``TextNormalizer.normalize``.
        postal_code : str | None
            Seven-digit postal code written with the address, or ``None``.
        within : AddressCode | None
            Prefecture, municipality, or town the address must lie in, or ``None`` to
            search everywhere.

        Returns
        -------
        MatchOutcome
            The match, or the ``AddressNotFoundError`` or ``AmbiguousAddressError`` that
            ``match`` would raise.

        Raises
        ------
        DatasetNotImportedError
            If the repository contains no towns.
        """
        outcome = self._resolve(normalized_address, postal_code, within)
        if (
            within is not None
            and isinstance(outcome, AddressMatch)
            and not within.contains(outcome.code)
        ):
            return self._outside(normalized_address, within)
        return outcome

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
        outcome = self.interpret(normalized_address, postal_code)
        return outcome if isinstance(outcome, AddressMatch) else None

    def _resolve(
        self, normalized_address: str, postal_code: str | None, within: AddressCode | None
    ) -> MatchOutcome:
        written_matches = self._match_municipalities(normalized_address)
        municipality_matches = [
            narrowed
            for municipality_match in written_matches
            if (
                narrowed := self._narrow_by_postal_code(
                    self._narrow_by_area(municipality_match, within), postal_code
                )
            ).municipalities
        ]
        if not municipality_matches:
            outcome = self._match_without_municipality(normalized_address, postal_code, within)
            if within is not None and written_matches and isinstance(outcome, AddressNotFoundError):
                return self._outside(normalized_address, within)
            return outcome
        longest_match = municipality_matches[0]
        if not NameIndex.strip_prefix(longest_match.remainder):
            return self._match_municipality_only(normalized_address, postal_code, longest_match)
        for municipality_match in municipality_matches:
            is_town_required = (
                municipality_match.is_town_required or municipality_match is not longest_match
            )
            interpretations = self._interpret_town(
                municipality_match, within, is_town_required=is_town_required
            )
            if interpretations:
                return self._select(
                    normalized_address, postal_code, municipality_match, interpretations
                )
        return AddressNotFoundError(
            f"No town in {self._describe_all(longest_match.municipalities)} matches "
            + f"{longest_match.remainder!r}."
        )

    def _outside(self, normalized_address: str, within: AddressCode) -> AddressNotFoundError:
        return AddressNotFoundError(f"{normalized_address!r} does not lie within {within}.")

    def _match_without_municipality(
        self, text: str, postal_code: str | None, within: AddressCode | None
    ) -> MatchOutcome:
        index = self._name_index.prefectures
        keys = self._matching_prefixes(self._normalizer.fold(text), index)
        prefecture = index[keys[0]] if keys else None
        remainder = text[len(keys[0]) :] if keys else text
        if prefecture is not None and not remainder:
            return AddressMatch(
                address=Address(prefecture=prefecture),
                remainder="",
                normalized_address=text,
                postal_code=postal_code,
                town_name_tier=None,
            )
        town_outcome = self._match_town_only(text, remainder, postal_code, prefecture, within)
        if town_outcome is not None:
            return town_outcome
        if prefecture is None:
            return AddressNotFoundError(f"No prefecture, municipality, or town matches {text!r}.")
        return AddressNotFoundError(
            f"No municipality or town in {prefecture.name} matches {remainder!r}."
        )

    def _match_town_only(
        self,
        normalized_address: str,
        text: str,
        postal_code: str | None,
        prefecture: Prefecture | None,
        within: AddressCode | None,
    ) -> MatchOutcome | None:
        index = self._get_oaza_municipality_index()
        municipalities_by_code = self._get_municipalities_by_code()
        comparable_text = self._fold_town_text(text)
        skipped_length = len(text) - len(comparable_text)
        candidates: dict[str, Municipality] = {}
        for key in self._matching_prefixes(comparable_text, index):
            municipalities = self._narrow_by_postal_code(
                MunicipalityMatch(
                    name="",
                    municipalities=[
                        municipalities_by_code[lg_code]
                        for lg_code in sorted(index[key])
                        if (
                            prefecture is None
                            or municipalities_by_code[lg_code].prefecture_name == prefecture.name
                        )
                        and self._overlaps(municipalities_by_code[lg_code], within)
                    ],
                    remainder=text,
                    is_name_abbreviated=True,
                ),
                postal_code,
            ).municipalities
            if len(municipalities) <= self._TOWN_ONLY_MUNICIPALITY_LIMIT:
                candidates.update((item.lg_code, item) for item in municipalities)
            elif self._TOWN_NAME_END.match(text[skipped_length + len(key) :]):
                return AmbiguousAddressError(
                    f"The town name of {text!r} is found in {len(municipalities)} "
                    + "municipalities. Add the municipality.",
                    tuple(AddressCode(lg_code=item.lg_code) for item in municipalities),
                )
        if not candidates:
            return None
        municipality_match = MunicipalityMatch(
            name="",
            municipalities=[candidates[lg_code] for lg_code in sorted(candidates)],
            remainder=text,
            is_name_abbreviated=True,
        )
        interpretations = [
            item
            for item in self._interpret_town(municipality_match, within, is_town_required=True)
            if item.lot.numbers or not item.remainder
        ]
        if not interpretations:
            return None
        return self._select(normalized_address, postal_code, municipality_match, interpretations)

    def _match_municipalities(self, text: str) -> list[MunicipalityMatch]:
        name_index = self._name_index
        index = name_index.municipalities
        ward_index = name_index.wards
        folded = self._normalizer.fold(text)
        full_name_matches = [
            self._to_municipality_match(
                text, key, index[key], is_name_abbreviated=key in name_index.abbreviated_keys
            )
            for key in self._matching_prefixes(folded, index)
        ]
        ward_matches = [
            self._to_municipality_match(text, key, ward_index[key], is_name_abbreviated=False)
            for key in self._matching_prefixes(folded, ward_index)
        ]
        return full_name_matches + ward_matches

    def _to_municipality_match(
        self,
        text: str,
        key: str,
        municipalities: frozenset[Municipality],
        *,
        is_name_abbreviated: bool,
    ) -> MunicipalityMatch:
        return MunicipalityMatch(
            name=text[: len(key)],
            municipalities=sorted(municipalities, key=lambda municipality: municipality.lg_code),
            remainder=text[len(key) :],
            is_name_abbreviated=is_name_abbreviated,
        )

    def _narrow_by_area(
        self, municipality_match: MunicipalityMatch, within: AddressCode | None
    ) -> MunicipalityMatch:
        if within is None:
            return municipality_match
        selected = [
            municipality
            for municipality in municipality_match.municipalities
            if self._overlaps(municipality, within)
        ]
        return replace(
            municipality_match,
            municipalities=selected,
            is_name_abbreviated=municipality_match.is_name_abbreviated
            and (len(selected) > 1 or any(municipality.ward_name for municipality in selected)),
        )

    def _overlaps(self, municipality: Municipality, within: AddressCode | None) -> bool:
        if within is None:
            return True
        code = AddressCode(lg_code=municipality.lg_code)
        return within.contains(code) or code.contains(within)

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
            is_name_abbreviated=municipality_match.is_name_abbreviated
            and (len(selected) > 1 or any(municipality.ward_name for municipality in selected)),
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
        self,
        municipality_match: MunicipalityMatch,
        within: AddressCode | None,
        *,
        is_town_required: bool,
    ) -> list[TownInterpretation]:
        return [
            narrowed
            for municipality in municipality_match.municipalities
            for interpretation in self._interpret_all(municipality, municipality_match.remainder)
            if not is_town_required or interpretation.name_length > 0
            if (narrowed := self._narrow_towns_by_area(interpretation, within)).towns
        ]

    def _narrow_towns_by_area(
        self, interpretation: TownInterpretation, within: AddressCode | None
    ) -> TownInterpretation:
        if within is None:
            return interpretation
        return replace(
            interpretation,
            towns=[
                town
                for town in interpretation.towns
                if within.contains(AddressCode(lg_code=town.lg_code, machiaza_id=town.machiaza_id))
            ],
        )

    def _select(
        self,
        normalized_address: str,
        postal_code: str | None,
        municipality_match: MunicipalityMatch,
        interpretations: list[TownInterpretation],
    ) -> MatchOutcome:
        text = municipality_match.remainder
        best_key = min(interpretation.ranking_key for interpretation in interpretations)
        best = [item for item in interpretations if item.ranking_key == best_key]
        if postal_code is not None:
            best = self._prefer_postal_code(best, postal_code)
        towns = {(town.lg_code, town.machiaza_id): town for item in best for town in item.towns}
        lots = {item.lot for item in best}
        candidates = self._candidate_codes(best)
        if len(towns) == 1 and len(lots) > 1:
            municipality = next(iter(towns.values())).municipality
            return AmbiguousAddressError(
                f"Lot numbers of {text!r} in {self._describe(municipality)} are ambiguous: "
                + f"{sorted(map(str, lots))}.",
                candidates,
            )
        if len(towns) > 1:
            names = sorted(
                f"{self._describe(town.municipality)}{town.oaza_name}{town.chome_name}"
                + f"{town.koaza_name}({town.lg_code}-{town.machiaza_id})"
                for town in towns.values()
            )
            return AmbiguousAddressError(f"{text!r} is ambiguous: {names}.", candidates)
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

    def _get_oaza_municipality_index(self) -> dict[str, set[str]]:
        if self._oaza_municipality_index is None:
            index: dict[str, set[str]] = defaultdict(set)
            for oaza_name, lg_codes in self._repository.map_oaza_names().items():
                for normalized_name in self._normalizer.normalize_name(oaza_name):
                    key = self._fold_town_text(normalized_name)
                    if key:
                        index[key].update(lg_codes)
            self._oaza_municipality_index = dict(index)
        return self._oaza_municipality_index

    def _get_municipalities_by_code(self) -> dict[str, Municipality]:
        if self._municipalities_by_code is None:
            self._municipalities_by_code = {
                municipality.lg_code: municipality
                for municipality in self._repository.list_municipalities()
            }
        return self._municipalities_by_code

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

    def _fold_town_text(self, normalized_text: str) -> str:
        return self._normalizer.fold(NameIndex.strip_prefix(normalized_text))

    def _matching_prefixes(self, text: str, keys: Container[str]) -> list[str]:
        return [text[:length] for length in range(len(text), 0, -1) if text[:length] in keys]

    def _describe(self, municipality: Municipality) -> str:
        return municipality.prefecture_name + municipality.city_name + municipality.ward_name

    def _describe_all(self, municipalities: list[Municipality]) -> str:
        return ", ".join(self._describe(municipality) for municipality in municipalities)
