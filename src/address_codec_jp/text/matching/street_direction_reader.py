import re
from collections.abc import Sequence
from dataclasses import replace
from typing import ClassVar

from address_codec_jp.address import Town
from address_codec_jp.results import MatchTier
from address_codec_jp.text.matching.candidate_set import CandidateSet
from address_codec_jp.text.normalization import TextNormalizer


class StreetDirectionReader:
    """
    Reader of the street directions of Kyoto (通り名) in normalized address text.

    A street direction names a street and usually a crossing street, and mostly ends
    with a direction (``上る``, ``下る``, ``東入``, ``西裏``, ``北側``), which may be
    repeated and followed by a count of blocks (``烏丸通七条下る西入``, ``下る二筋目``).
    It is compared with the koaza of the towns that ``Town.is_street_direction`` marks,
    strictly first and then with notation variants folded: ``通`` and ``通り`` are
    dropped, ``上ル`` and ``上がる`` read as ``上る``, ``下ル`` and ``下がる`` as ``下る``,
    and ``入ル`` and ``入る`` as ``入``. A registered direction may end anywhere; a
    written direction that is not registered is recognized only where a direction ends.

    Parameters
    ----------
    normalizer : TextNormalizer
        Normalizer applied to registry names.
    """

    _DIRECTION: ClassVar[re.Pattern[str]] = re.compile(
        r"(?P<direction>上がる|上ル|上る|下がる|下ル|下る|[東西南北](?:入[ルる]?|裏|側))"
        + r"(?P<count>[0-9一二三四五六七八九十]+(?:丁目|丁|筋目)(?:入[ルる]?)?)?"
    )
    _STREET_SEPARATOR: ClassVar[re.Pattern[str]] = re.compile(r"通り|通|\|")
    _VARIANTS: ClassVar[tuple[tuple[str, str], ...]] = (
        ("通り", ""),
        ("通", ""),
        ("上がる", "上る"),
        ("上ル", "上る"),
        ("下がる", "下る"),
        ("下ル", "下る"),
        ("入ル", "入"),
        ("入る", "入"),
    )

    def __init__(self, normalizer: TextNormalizer) -> None:
        self._normalizer: TextNormalizer = normalizer
        self._names: dict[tuple[str, str], frozenset[str]] = {}
        self._folded_names: dict[tuple[str, str], frozenset[str]] = {}

    def fold_names(self, towns: Sequence[Town]) -> frozenset[str]:
        """
        Collect the folded street directions of towns, to find where they end in a text.

        Parameters
        ----------
        towns : Sequence[Town]
            Towns whose street directions are collected; other towns are skipped.

        Returns
        -------
        frozenset[str]
            Folded names of every street direction among ``towns``.
        """
        return frozenset(
            name
            for town in towns
            if town.is_street_direction
            for name in self._folded_names_of(town)
        )

    def split_points(self, normalized_text: str, street_keys: frozenset[str]) -> list[int]:
        """
        List the positions where a street direction at the start of a text may end.

        Parameters
        ----------
        normalized_text : str
            Text normalized by ``TextNormalizer.normalize``.
        street_keys : frozenset[str]
            Registered street directions as returned by ``fold_names``.

        Returns
        -------
        list[int]
            End of every written direction, with and without the count of blocks after
            it, since an oaza may be named like a count (``四丁目``), and of every
            registered street direction that starts the text, in ascending order.
        """
        ends = {
            end
            for matched in self._DIRECTION.finditer(normalized_text)
            for end in (matched.end("direction"), matched.end())
        }
        return sorted(ends | self._registered_ends(normalized_text, street_keys))

    def match(self, normalized_street: str, towns: Sequence[Town]) -> CandidateSet | None:
        """
        Find the towns whose street direction is a written street direction.

        Parameters
        ----------
        normalized_street : str
            Whole written street direction, normalized.
        towns : Sequence[Town]
            Towns to compare; only street directions among them can match.

        Returns
        -------
        CandidateSet | None
            Strictly matching towns at ``MatchTier.EXACT``, else towns matching with
            folded variants at ``MatchTier.FOLDED``, with an empty remainder; ``None``
            when no town matches.
        """
        streets = [town for town in towns if town.is_street_direction]
        exact = [town for town in streets if normalized_street in self._names_of(town)]
        if exact:
            return CandidateSet(towns=exact, remainder="", penalty=0, loosest_tier=MatchTier.EXACT)
        folded_street = self._fold(normalized_street)
        folded = [town for town in streets if folded_street in self._folded_names_of(town)]
        if folded:
            return CandidateSet(
                towns=folded,
                remainder="",
                penalty=MatchTier.FOLDED.penalty,
                loosest_tier=MatchTier.FOLDED,
            )
        return None

    def match_all(self, normalized_text: str, towns: Sequence[Town]) -> list[CandidateSet]:
        """
        Find every registered street direction that starts a text.

        Parameters
        ----------
        normalized_text : str
            Text normalized by ``TextNormalizer.normalize``.
        towns : Sequence[Town]
            Towns to compare; only street directions among them can match.

        Returns
        -------
        list[CandidateSet]
            One candidate set per matching length, with the text after the direction as
            remainder.
        """
        return [
            replace(candidates, remainder=normalized_text[end:])
            for end in sorted(self._registered_ends(normalized_text, self.fold_names(towns)))
            if (candidates := self.match(normalized_text[:end], towns)) is not None
        ]

    def _registered_ends(self, normalized_text: str, street_keys: frozenset[str]) -> set[int]:
        if not street_keys:
            return set()
        return {
            end
            for end in range(1, len(normalized_text) + 1)
            if self._fold(normalized_text[:end]) in street_keys
        }

    def find_closest_oazas(self, normalized_street: str, towns: Sequence[Town]) -> list[Town]:
        """
        Select the oaza whose registered street directions resemble an unregistered one.

        Only oaza with registered street directions are considered. Resemblance to the
        closest street direction of an oaza is the number of street names they share,
        in any order, so that a direction written from the other street of a crossing
        (``竹屋町通烏丸西入`` for ``烏丸通竹屋町西入``) still counts; ties are broken by the
        number of character pairs that their folded texts share. An oaza none of whose
        street directions shares a street name with the written one is not selected.

        Parameters
        ----------
        normalized_street : str
            Whole written street direction, normalized.
        towns : Sequence[Town]
            Towns that bear the oaza name written after the direction.

        Returns
        -------
        list[Town]
            Oaza-level towns that resemble the direction most; several when they tie,
            empty when no oaza among ``towns`` has a street direction that shares a
            street name with it.
        """
        oaza_towns = {
            town.machiaza_id[:4]: town
            for town in towns
            if town.is_registered and not town.koaza_name and town.chome_number is None
        }
        written_names = self._street_names(normalized_street)
        written_pairs = self._character_pairs(self._fold(normalized_street))
        scores: dict[str, tuple[int, int]] = {}
        for town in towns:
            oaza_part = town.machiaza_id[:4]
            if town.is_street_direction and oaza_part in oaza_towns:
                score = max(
                    (
                        len(written_names & self._street_names(name)),
                        len(written_pairs & self._character_pairs(self._fold(name))),
                    )
                    for name in self._names_of(town)
                )
                if score[0] > 0:
                    scores[oaza_part] = max(scores.get(oaza_part, score), score)
        if not scores:
            return []
        best_score = max(scores.values())
        return [oaza_towns[part] for part, score in scores.items() if score == best_score]

    def _street_names(self, normalized_street: str) -> frozenset[str]:
        folded = self._normalizer.fold(normalized_street)
        return frozenset(
            name for name in self._STREET_SEPARATOR.split(self._DIRECTION.sub("|", folded)) if name
        )

    def _names_of(self, town: Town) -> frozenset[str]:
        key = (town.lg_code, town.machiaza_id)
        if key not in self._names:
            self._names[key] = frozenset(self._normalizer.normalize_name(town.koaza_name))
        return self._names[key]

    def _folded_names_of(self, town: Town) -> frozenset[str]:
        key = (town.lg_code, town.machiaza_id)
        if key not in self._folded_names:
            self._folded_names[key] = frozenset(self._fold(name) for name in self._names_of(town))
        return self._folded_names[key]

    def _fold(self, normalized_street: str) -> str:
        folded = self._normalizer.fold(normalized_street)
        for variant, replacement in self._VARIANTS:
            folded = folded.replace(variant, replacement)
        return folded

    def _character_pairs(self, text: str) -> set[str]:
        return {text[index : index + 2] for index in range(len(text) - 1)}
