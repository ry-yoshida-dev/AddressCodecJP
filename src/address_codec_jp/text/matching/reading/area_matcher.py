import re
from dataclasses import replace
from typing import ClassVar

from address_codec_jp.address import Address, AddressCode, Municipality, Prefecture
from address_codec_jp.errors import (
    AddressNotFoundError,
    AmbiguousAddressError,
)
from address_codec_jp.results import AddressMatch
from address_codec_jp.text.matching.index.municipality_name_index import MunicipalityNameIndex
from address_codec_jp.text.matching.index.name_index import NameIndex
from address_codec_jp.text.matching.index.town_name_index import TownNameIndex
from address_codec_jp.text.matching.reading.municipality_match import MunicipalityMatch
from address_codec_jp.text.matching.reading.municipality_reader import MunicipalityReader
from address_codec_jp.text.matching.reading.town_interpretation import TownInterpretation
from address_codec_jp.text.matching.reading.town_reader import TownReader
from address_codec_jp.text.matching.town_source import TownSource
from address_codec_jp.text.normalization import LotNumberParser, TextNormalizer

type MatchOutcome = AddressMatch | AddressNotFoundError | AmbiguousAddressError


class AreaMatcher:
    """
    Matcher from a normalized address to the most specific registered area.

    The prefecture or municipality is read by ``MunicipalityReader``, longest name first.
    When no town of the longest municipality matches the rest, shorter municipality names
    are tried, and a town name must then confirm the municipality. When a name fits
    several municipalities, such as a designated city without its ward
    (``横浜市山下町``), the town name must decide among them. An address that starts with
    no municipality name is read as a town name, optionally after the prefecture
    (``霞が関1-1-1``): every municipality with an oaza that starts the text, or with a
    street direction followed by one of its oaza names, is tried, and the reading must
    include lot numbers or end with the town name. An oaza name followed by a number or
    the end of the text and found in too many municipalities (``本町1-1``) rejects the
    address as ambiguous.

    The text after the municipality is read by ``TownReader``, and the best
    ``TownInterpretation`` wins. When the best readings point to different towns or lot
    numbers, the address is rejected as ambiguous instead of picking one. A postal code
    given with the address decides only between such equally ranked readings, and
    between municipalities that share a name. An area given as ``within`` discards every
    municipality and town outside it before the readings are ranked. A designated city
    written without its ward still needs a town name when the postal code or ``within``
    leaves only one of its wards.

    A partial match, when allowed, ends at the deepest town, municipality, or prefecture
    whose name was read and keeps the rest as the remainder, where the address would
    otherwise not be found (``萩市`` with the remainder ``麻生``). Partial town readings are
    tried only for the longest municipality name, and when they point to several towns
    the match ends at the municipality. A municipality name that needs a town to decide
    stays ambiguous.

    Parameters
    ----------
    repository : TownSource
        Source of municipalities and towns, such as ``TownRepository``.
    normalizer : TextNormalizer
        Normalizer applied to registry names.
    lot_parser : LotNumberParser
        Parser for the numbers after the town name.
    """

    _TOWN_ONLY_MUNICIPALITY_LIMIT: ClassVar[int] = 50
    _TOWN_NAME_END: ClassVar[re.Pattern[str]] = re.compile(r"$|[0-9-]")

    def __init__(
        self, repository: TownSource, normalizer: TextNormalizer, lot_parser: LotNumberParser
    ) -> None:
        self._municipalities: MunicipalityReader = MunicipalityReader(repository, normalizer)
        self._town_names: TownNameIndex = TownNameIndex(repository, normalizer)
        self._towns: TownReader = TownReader(self._town_names, normalizer, lot_parser)

    @property
    def municipality_names(self) -> MunicipalityNameIndex:
        """Prefecture and municipality names of the repository, built on first use."""
        return self._municipalities.names

    def match(
        self,
        normalized_address: str,
        postal_code: str | None,
        *,
        within: AddressCode | None = None,
        is_partial_match_allowed: bool = False,
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
        is_partial_match_allowed : bool
            Whether an address whose town is not found matches its municipality or
            prefecture, with the unread text as the remainder.

        Returns
        -------
        AddressMatch
            Matched prefecture, municipality, town, lot numbers, and unconsumed text.

        Raises
        ------
        AddressNotFoundError
            If nothing matches, or only the municipality or prefecture does and partial
            matches are not allowed.
        AmbiguousAddressError
            If the address fits several areas or lot numbers equally well.
        DatasetNotImportedError
            If the repository contains no towns.
        """
        outcome = self.interpret(
            normalized_address,
            postal_code,
            within=within,
            is_partial_match_allowed=is_partial_match_allowed,
        )
        if isinstance(outcome, AddressMatch):
            return outcome
        raise outcome

    def interpret(
        self,
        normalized_address: str,
        postal_code: str | None,
        *,
        within: AddressCode | None = None,
        is_partial_match_allowed: bool = False,
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
        is_partial_match_allowed : bool
            Whether an address whose town is not found matches its municipality or
            prefecture, with the unread text as the remainder.

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
        outcome = self._resolve(
            normalized_address,
            postal_code,
            within,
            is_partial_match_allowed=is_partial_match_allowed,
        )
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
        self,
        normalized_address: str,
        postal_code: str | None,
        within: AddressCode | None,
        *,
        is_partial_match_allowed: bool,
    ) -> MatchOutcome:
        written_matches = self._municipalities.match_all(normalized_address)
        municipality_matches = [
            narrowed
            for municipality_match in written_matches
            if (
                narrowed := self._municipalities.narrow(municipality_match, within, postal_code)
            ).municipalities
        ]
        if not municipality_matches:
            outcome = self._match_without_municipality(
                normalized_address,
                postal_code,
                within,
                is_partial_match_allowed=is_partial_match_allowed,
            )
            if within is not None and written_matches and isinstance(outcome, AddressNotFoundError):
                return self._outside(normalized_address, within)
            return outcome
        longest_match = municipality_matches[0]
        if not NameIndex.strip_prefix(longest_match.remainder):
            return self._match_municipality_only(
                normalized_address, postal_code, longest_match, remainder=""
            )
        for municipality_match in municipality_matches:
            is_town_required = (
                municipality_match.is_town_required or municipality_match is not longest_match
            )
            interpretations = self._towns.interpret(
                municipality_match, within, is_town_required=is_town_required
            )
            if interpretations:
                return self._select(
                    normalized_address, postal_code, municipality_match, interpretations
                )
        if is_partial_match_allowed:
            return self._match_partially(normalized_address, postal_code, within, longest_match)
        return AddressNotFoundError(
            f"No town in {self._describe_all(longest_match.municipalities)} matches "
            + f"{longest_match.remainder!r}."
        )

    def _match_partially(
        self,
        normalized_address: str,
        postal_code: str | None,
        within: AddressCode | None,
        municipality_match: MunicipalityMatch,
    ) -> MatchOutcome:
        interpretations = self._towns.interpret(
            municipality_match,
            within,
            is_town_required=municipality_match.is_town_required,
            is_partial=True,
        )
        if interpretations:
            outcome = self._select(
                normalized_address, postal_code, municipality_match, interpretations
            )
            if isinstance(outcome, AddressMatch):
                return outcome
        return self._match_municipality_only(
            normalized_address,
            postal_code,
            municipality_match,
            remainder=municipality_match.remainder,
        )

    def _outside(self, normalized_address: str, within: AddressCode) -> AddressNotFoundError:
        return AddressNotFoundError(f"{normalized_address!r} does not lie within {within}.")

    def _match_without_municipality(
        self,
        text: str,
        postal_code: str | None,
        within: AddressCode | None,
        *,
        is_partial_match_allowed: bool,
    ) -> MatchOutcome:
        prefecture, remainder = self._municipalities.match_prefecture(text)
        if prefecture is not None and not remainder:
            return self._match_prefecture_only(text, postal_code, prefecture, remainder="")
        town_outcome = self._match_town_only(text, remainder, postal_code, prefecture, within)
        if town_outcome is not None:
            return town_outcome
        if prefecture is not None and is_partial_match_allowed:
            return self._match_prefecture_only(text, postal_code, prefecture, remainder=remainder)
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
        index = self._town_names.oaza_municipality_codes
        municipalities_by_code = self._town_names.municipalities_by_code
        comparable_text = self._town_names.fold(text)
        skipped_length = len(text) - len(comparable_text)
        candidates: dict[str, Municipality] = {}
        for key in MunicipalityReader.matching_prefixes(comparable_text, index):
            municipalities = self._municipalities.narrow_by_postal_code(
                self._abbreviated_match(
                    [
                        municipalities_by_code[lg_code]
                        for lg_code in sorted(index[key])
                        if self._is_candidate(municipalities_by_code[lg_code], prefecture, within)
                    ],
                    text,
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
        for municipality in self._street_municipalities(text, postal_code, prefecture, within):
            _ = candidates.setdefault(municipality.lg_code, municipality)
        if not candidates:
            return None
        municipality_match = self._abbreviated_match(
            [candidates[lg_code] for lg_code in sorted(candidates)], text
        )
        interpretations = [
            item
            for item in self._towns.interpret(municipality_match, within, is_town_required=True)
            if item.lot.numbers or not item.remainder
        ]
        if not interpretations:
            return None
        return self._select(normalized_address, postal_code, municipality_match, interpretations)

    def _street_municipalities(
        self,
        text: str,
        postal_code: str | None,
        prefecture: Prefecture | None,
        within: AddressCode | None,
    ) -> list[Municipality]:
        municipalities_by_code = self._town_names.municipalities_by_code
        municipalities = [
            municipality
            for municipality in (
                municipalities_by_code[lg_code]
                for lg_code in sorted(self._town_names.street_municipality_codes)
            )
            if self._is_candidate(municipality, prefecture, within)
            and self._towns.has_street_before_oaza(municipality, text)
        ]
        return self._municipalities.narrow_by_postal_code(
            self._abbreviated_match(municipalities, text), postal_code
        ).municipalities

    def _is_candidate(
        self, municipality: Municipality, prefecture: Prefecture | None, within: AddressCode | None
    ) -> bool:
        return (
            prefecture is None or municipality.prefecture_name == prefecture.name
        ) and MunicipalityReader.overlaps(municipality, within)

    def _abbreviated_match(
        self, municipalities: list[Municipality], text: str
    ) -> MunicipalityMatch:
        return MunicipalityMatch(
            name="", municipalities=municipalities, remainder=text, is_name_abbreviated=True
        )

    def _match_prefecture_only(
        self,
        normalized_address: str,
        postal_code: str | None,
        prefecture: Prefecture,
        *,
        remainder: str,
    ) -> AddressMatch:
        return AddressMatch(
            address=Address(prefecture=prefecture),
            remainder=remainder,
            normalized_address=normalized_address,
            postal_code=postal_code,
            town_name_tier=None,
        )

    def _match_municipality_only(
        self,
        normalized_address: str,
        postal_code: str | None,
        municipality_match: MunicipalityMatch,
        *,
        remainder: str,
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
            remainder=remainder,
            normalized_address=normalized_address,
            postal_code=postal_code,
            town_name_tier=None,
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

    def _describe(self, municipality: Municipality) -> str:
        return municipality.prefecture_name + municipality.city_name + municipality.ward_name

    def _describe_all(self, municipalities: list[Municipality]) -> str:
        return ", ".join(self._describe(municipality) for municipality in municipalities)
