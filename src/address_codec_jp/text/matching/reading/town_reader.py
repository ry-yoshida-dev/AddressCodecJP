import re
from dataclasses import replace
from typing import ClassVar

from address_codec_jp.address import AddressCode, LotNumber, Municipality, Town
from address_codec_jp.results import MatchTier
from address_codec_jp.text.matching.index.candidate_set import CandidateSet
from address_codec_jp.text.matching.index.name_index import NameIndex
from address_codec_jp.text.matching.index.town_name_index import TownNameIndex
from address_codec_jp.text.matching.reading.municipality_match import MunicipalityMatch
from address_codec_jp.text.matching.reading.street_direction_reader import StreetDirectionReader
from address_codec_jp.text.matching.reading.town_interpretation import TownInterpretation
from address_codec_jp.text.normalization import LotNumberParser, TextNormalizer


class TownReader:
    """
    Reader of the town and lot numbers in the text after a municipality.

    Every combination of oaza, chome, koaza, and lot numbers is tried, and each complete
    reading becomes a ``TownInterpretation``. A reading is discarded when it reads no lot
    numbers but leaves digits unread (``浅草`` + ``橋6-1-1``) other than a floor or
    building number (``一番町`` + ``3階`` is kept), leaves a chome number unread, or puts
    lot numbers on an oaza-level town that the registry divides into chome. A partial
    reading keeps such a reading as its town without lot numbers, with the text after
    the town name as the remainder (``勝浦`` + ``字家六2094番地1``).

    A street direction of Kyoto (``Town.is_street_direction``) is read both after the
    oaza name, as the registry orders them, and before it, as addresses in Kyoto are
    usually written (``烏丸通塩小路下る東塩小路町``). A written direction that matches no
    registered one is skipped before an oaza with a street direction that shares a
    street name with it, and decides between oaza of the same name by its resemblance
    to theirs, at ``MatchTier.FOLDED`` and below every registered reading. Lot numbers
    belong to the oaza, so an address with lot numbers is matched to the oaza of its
    street direction when the registry lists that oaza, and to the street direction
    itself otherwise.

    Parameters
    ----------
    town_names : TownNameIndex
        Oaza and koaza names of the towns.
    normalizer : TextNormalizer
        Normalizer applied to the street directions.
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
    _UNREGISTERED_STREET_PENALTY: ClassVar[int] = MatchTier.FOLDED.penalty + 1

    def __init__(
        self, town_names: TownNameIndex, normalizer: TextNormalizer, lot_parser: LotNumberParser
    ) -> None:
        self._town_names: TownNameIndex = town_names
        self._lot_parser: LotNumberParser = lot_parser
        self._streets: StreetDirectionReader = StreetDirectionReader(normalizer)
        self._street_keys_by_municipality: dict[str, frozenset[str]] = {}

    def interpret(
        self,
        municipality_match: MunicipalityMatch,
        within: AddressCode | None,
        *,
        is_town_required: bool,
        is_partial: bool = False,
    ) -> list[TownInterpretation]:
        """
        Read the text after a municipality in every way that the registry allows.

        Parameters
        ----------
        municipality_match : MunicipalityMatch
            Municipalities and the text after their name.
        within : AddressCode | None
            Area the towns must lie in, or ``None`` to keep every town.
        is_town_required : bool
            Whether a reading must include a town name.
        is_partial : bool
            Whether a reading that would be discarded is kept as its town with the text
            after the town name as the remainder. Partial readings include a town name.

        Returns
        -------
        list[TownInterpretation]
            Complete readings with their towns in ``within``.
        """
        return [
            narrowed
            for municipality in municipality_match.municipalities
            for interpretation in self._interpret_all(
                municipality, municipality_match.remainder, is_partial=is_partial
            )
            if not (is_town_required or is_partial) or interpretation.name_length > 0
            if (narrowed := self._narrow_by_area(interpretation, within)).towns
        ]

    def has_street_before_oaza(self, municipality: Municipality, text: str) -> bool:
        """
        Tell whether a text starts with a street direction followed by an oaza name.

        Parameters
        ----------
        municipality : Municipality
            Municipality whose street directions and oaza are tried.
        text : str
            Normalized text that may start with a street direction.

        Returns
        -------
        bool
            ``True`` when such a reading exists.
        """
        return bool(
            self._street_first_options(
                municipality, self._town_names.oazas(municipality.lg_code), text
            )
        )

    def _narrow_by_area(
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

    def _interpret_all(
        self, municipality: Municipality, text: str, *, is_partial: bool
    ) -> list[TownInterpretation]:
        oaza_index = self._town_names.oazas(municipality.lg_code)
        readings = [
            town_candidates
            for oaza_candidates in oaza_index.match_all(text)
            for chome_candidates in self._chome_options(oaza_candidates)
            for town_candidates in self._koaza_options(chome_candidates)
        ]
        readings.extend(
            chome_candidates
            for street_candidates in self._street_first_options(municipality, oaza_index, text)
            for chome_candidates in self._chome_options(street_candidates)
        )
        return [
            interpretation
            for town_candidates in readings
            if (
                interpretation := self._interpret(town_candidates, len(text), is_partial=is_partial)
            )
            is not None
        ]

    def _street_first_options(
        self, municipality: Municipality, oaza_index: NameIndex, text: str
    ) -> list[CandidateSet]:
        street_keys = self._street_keys(municipality)
        if not street_keys:
            return []
        options: list[CandidateSet] = []
        for end in self._streets.split_points(text, street_keys):
            street, rest = text[:end], text[end:]
            for oaza_candidates in oaza_index.match_all(rest):
                if oaza_candidates.remainder != rest:
                    options.extend(self._read_street_before_oaza(street, oaza_candidates))
        return options

    def _street_keys(self, municipality: Municipality) -> frozenset[str]:
        lg_code = municipality.lg_code
        if lg_code not in self._street_keys_by_municipality:
            self._street_keys_by_municipality[lg_code] = self._streets.fold_names(
                self._town_names.list_street_directions(lg_code)
            )
        return self._street_keys_by_municipality[lg_code]

    def _read_street_before_oaza(
        self, street: str, oaza_candidates: CandidateSet
    ) -> list[CandidateSet]:
        registered = self._streets.match(street, oaza_candidates.towns)
        if registered is not None:
            return [
                replace(
                    oaza_candidates,
                    towns=registered.towns,
                    penalty=oaza_candidates.penalty + registered.penalty,
                    loosest_tier=oaza_candidates.loosest_tier.loosen(registered.loosest_tier),
                )
            ]
        oaza_towns = self._streets.find_closest_oazas(street, oaza_candidates.towns)
        if not oaza_towns:
            return []
        return [
            replace(
                oaza_candidates,
                towns=oaza_towns,
                penalty=oaza_candidates.penalty + self._UNREGISTERED_STREET_PENALTY,
                loosest_tier=MatchTier.FOLDED,
            )
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
                    replace(
                        candidates,
                        towns=selected,
                        remainder=candidates.remainder[matched.end() :],
                    )
                )
        without_chome = [town for town in candidates.towns if town.chome_number is None]
        if without_chome:
            options.append(replace(candidates, towns=without_chome))
        return options

    def _koaza_options(self, candidates: CandidateSet) -> list[CandidateSet]:
        koaza_index = self._town_names.koazas(candidates.towns)
        options = [
            CandidateSet(
                towns=koaza_candidates.towns,
                remainder=koaza_candidates.remainder,
                penalty=candidates.penalty + koaza_candidates.penalty,
                loosest_tier=candidates.loosest_tier.loosen(koaza_candidates.loosest_tier),
                split_digit_count=candidates.split_digit_count + koaza_candidates.split_digit_count,
            )
            for koaza_candidates in [
                *koaza_index.match_all(candidates.remainder),
                *self._streets.match_all(candidates.remainder, candidates.towns),
            ]
        ]
        without_koaza = [town for town in candidates.towns if not town.koaza_name]
        if without_koaza:
            options.append(replace(candidates, towns=without_koaza))
        return options

    def _interpret(
        self, candidates: CandidateSet, text_length: int, *, is_partial: bool
    ) -> TownInterpretation | None:
        lot_result = self._lot_parser.parse(candidates.remainder)
        if self._UNREAD_CHOME.match(lot_result.remainder) or (
            not lot_result.lot.numbers
            and not self._ASCII_DIGITS.isdisjoint(lot_result.remainder)
            and not self._lot_parser.is_building_number(lot_result.remainder)
        ):
            return self._interpret_partially(candidates, text_length) if is_partial else None
        towns = self._lot_towns(candidates.towns) if lot_result.lot.numbers else candidates.towns
        towns = [town for town in towns if town.is_registered or not lot_result.lot.numbers]
        if not towns:
            return None
        return TownInterpretation(
            towns=towns,
            lot=lot_result.lot,
            lot_notation=lot_result.notation,
            remainder=lot_result.remainder,
            name_length=text_length - len(candidates.remainder) - candidates.split_digit_count,
            penalty=candidates.penalty,
            loosest_tier=candidates.loosest_tier,
        )

    def _interpret_partially(
        self, candidates: CandidateSet, text_length: int
    ) -> TownInterpretation:
        return TownInterpretation(
            towns=candidates.towns,
            lot=LotNumber(),
            lot_notation=None,
            remainder=candidates.remainder,
            name_length=text_length - len(candidates.remainder) - candidates.split_digit_count,
            penalty=candidates.penalty,
            loosest_tier=candidates.loosest_tier,
        )

    def _lot_towns(self, towns: list[Town]) -> list[Town]:
        selected: dict[tuple[str, str], Town] = {}
        for town in towns:
            oaza = self._town_names.find_oaza(town) if town.is_street_direction else None
            lot_town = oaza if oaza is not None and oaza.is_registered else town
            _ = selected.setdefault((lot_town.lg_code, lot_town.machiaza_id), lot_town)
        return list(selected.values())
