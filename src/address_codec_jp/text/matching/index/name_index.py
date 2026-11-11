import re
from collections import defaultdict
from typing import ClassVar

from address_codec_jp.address import Town
from address_codec_jp.results import MatchTier
from address_codec_jp.text.matching.index.candidate_set import CandidateSet
from address_codec_jp.text.normalization import KanjiNumeral, TextNormalizer


class NameIndex:
    """
    Tiered prefix index from registry names to towns.

    The registry sometimes registers names that differ only by a ``大字``/``字`` prefix or
    by ``の``/``ノ`` (e.g. ``大曲`` and ``字大曲``) as different towns. Addresses also add or
    leave out these markers inside a name (``哲多町大字大野`` for ``哲多町大野``,
    ``第10地割羅賀`` for ``第10地割字羅賀``), and at the folded tier a ``ノ`` or ``ケ``
    between kanji (``鷹ノ巣`` for ``鷹巣``) or a trailing ``町`` of a name when a number
    or the end of the text follows (``薄倉2364`` for ``薄倉町``). Each name is therefore
    indexed at every ``MatchTier``, and every prefix match is reported with the penalty of
    its tier so that the caller can rank complete readings. A match that ends in the middle
    of a number (koaza ``１`` before ``2番``) or right before a hyphenated number (koaza
    ``１２`` before ``-3``) records the digits it took, so that it cannot outrank reading
    those digits as a lot number. Towns registered with an empty name
    match any text without consuming it.

    Parameters
    ----------
    normalizer : TextNormalizer
        Normalizer applied to registry names.
    """

    _NAME_PREFIXES: ClassVar[tuple[str, ...]] = ("大字", "字")
    _NUMBER_CONTINUATION: ClassVar[re.Pattern[str]] = re.compile("-?[0-9]")
    # A 字 right after a numeral is part of a koaza name such as 1字 or 十字.
    _NAME_MARKERS: ClassVar[re.Pattern[str]] = re.compile(
        f"^字|[大小]字|(?<![0-9{KanjiNumeral.CHARACTERS}])字(?=.)"
    )

    _FOLDED_CONNECTIVES: ClassVar[re.Pattern[str]] = re.compile(
        f"(?<=[{TextNormalizer.KANJI_CHARACTERS}])[のケ](?=[{TextNormalizer.KANJI_CHARACTERS}])"
    )
    _OPTIONAL_NAME_SUFFIX: ClassVar[str] = "町"
    _MIN_STEM_LENGTH: ClassVar[int] = 2
    _STEM_END: ClassVar[re.Pattern[str]] = re.compile("$|-?[0-9]")

    def __init__(self, normalizer: TextNormalizer) -> None:
        self._normalizer: TextNormalizer = normalizer
        self._towns: dict[MatchTier, dict[str, list[Town]]] = {
            tier: defaultdict(list) for tier in MatchTier
        }
        self._stem_towns: dict[str, list[Town]] = defaultdict(list)
        self._unnamed_towns: list[Town] = []
        self._longest_key_length: int = 0

    def add(self, name: str, town: Town) -> None:
        """
        Register a town under a name.

        Parameters
        ----------
        name : str
            Registry name such as an oaza or koaza name. May be empty.
        town : Town
            Town reachable by the name.
        """
        normalized_names = self._normalizer.normalize_name(name) - {""}
        if not normalized_names:
            self._unnamed_towns.append(town)
            return
        for tier in MatchTier:
            keys = {self._to_comparable_text(item, tier)[0] for item in normalized_names}
            for key in keys:
                if key:
                    self._towns[tier][key].append(town)
                    self._longest_key_length = max(self._longest_key_length, len(key))
            if tier is MatchTier.FOLDED:
                for key in keys:
                    stem = key.removesuffix(self._OPTIONAL_NAME_SUFFIX)
                    if stem != key and len(stem) >= self._MIN_STEM_LENGTH:
                        self._stem_towns[stem].append(town)

    def match_all(self, normalized_text: str) -> list[CandidateSet]:
        """
        Find every registered name that starts the text.

        Parameters
        ----------
        normalized_text : str
            Text normalized by ``TextNormalizer.normalize``.

        Returns
        -------
        list[CandidateSet]
            One candidate set per matching name and tier, plus one for unnamed towns.
        """
        candidate_sets: list[CandidateSet] = []
        for tier in MatchTier:
            comparable_text, positions = self._to_comparable_text(normalized_text, tier)
            towns_by_key = self._towns[tier]
            for length in range(1, min(len(comparable_text), self._longest_key_length) + 1):
                key = comparable_text[:length]
                towns = towns_by_key.get(key, [])
                if tier is MatchTier.FOLDED and self._STEM_END.match(comparable_text[length:]):
                    towns = towns + self._stem_towns.get(key, [])
                if not towns:
                    continue
                remainder = normalized_text[positions[length - 1] + 1 :]
                candidate_sets.append(
                    CandidateSet(
                        towns=towns,
                        remainder=remainder,
                        penalty=tier.penalty,
                        loosest_tier=tier,
                        split_digit_count=self._count_split_digits(key, remainder),
                    )
                )
        if self._unnamed_towns:
            candidate_sets.append(
                CandidateSet(
                    towns=self._unnamed_towns,
                    remainder=normalized_text,
                    penalty=0,
                    loosest_tier=MatchTier.EXACT,
                )
            )
        return candidate_sets

    @classmethod
    def strip_prefix(cls, text: str) -> str:
        """
        Remove a leading ``大字`` or ``字``.

        Parameters
        ----------
        text : str
            Normalized text.

        Returns
        -------
        str
            Text without the prefix.
        """
        for prefix in cls._NAME_PREFIXES:
            if text.startswith(prefix):
                return text.removeprefix(prefix)
        return text

    def _count_split_digits(self, key: str, remainder: str) -> int:
        if self._NUMBER_CONTINUATION.match(remainder) is None:
            return 0
        return len(key) - len(key.rstrip("0123456789"))

    def _to_comparable_text(self, normalized_text: str, tier: MatchTier) -> tuple[str, list[int]]:
        """Build the comparable text of a tier with the index of each character in the input."""
        positions = list(range(len(normalized_text)))
        if tier is MatchTier.EXACT:
            return normalized_text, positions
        comparable_text, positions = self._remove(normalized_text, positions, self._NAME_MARKERS)
        if tier is MatchTier.FOLDED:
            comparable_text, positions = self._remove(
                self._normalizer.fold(comparable_text), positions, self._FOLDED_CONNECTIVES
            )
        return comparable_text, positions

    @staticmethod
    def _remove(text: str, positions: list[int], pattern: re.Pattern[str]) -> tuple[str, list[int]]:
        kept_text: list[str] = []
        kept_positions: list[int] = []
        start = 0
        for matched in pattern.finditer(text):
            kept_text.append(text[start : matched.start()])
            kept_positions.extend(positions[start : matched.start()])
            start = matched.end()
        kept_text.append(text[start:])
        kept_positions.extend(positions[start:])
        return "".join(kept_text), kept_positions
