import re
from collections import defaultdict
from typing import ClassVar

from address_codec_jp.domain.town import Town
from address_codec_jp.matching.candidate_set import CandidateSet
from address_codec_jp.matching.match_tier import MatchTier
from address_codec_jp.normalization.text_normalizer import TextNormalizer


class NameIndex:
    """
    Tiered prefix index from registry names to towns.

    The registry sometimes registers names that differ only by a ``大字``/``字`` prefix or
    by ``の``/``ノ`` (e.g. ``大曲`` and ``字大曲``) as different towns. Each name is therefore
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

    def __init__(self, normalizer: TextNormalizer) -> None:
        self._normalizer: TextNormalizer = normalizer
        self._towns: dict[MatchTier, dict[str, list[Town]]] = {
            tier: defaultdict(list) for tier in MatchTier
        }
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
            for key in {self._to_comparable_text(item, tier) for item in normalized_names}:
                if key:
                    self._towns[tier][key].append(town)
                    self._longest_key_length = max(self._longest_key_length, len(key))

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
            comparable_text = self._to_comparable_text(normalized_text, tier)
            skipped_length = len(normalized_text) - len(comparable_text)
            towns_by_key = self._towns[tier]
            for length in range(1, min(len(comparable_text), self._longest_key_length) + 1):
                key = comparable_text[:length]
                towns = towns_by_key.get(key)
                if towns is None:
                    continue
                remainder = normalized_text[skipped_length + len(key) :]
                candidate_sets.append(
                    CandidateSet(
                        towns=towns,
                        remainder=remainder,
                        penalty=tier.penalty,
                        split_digit_count=self._count_split_digits(key, remainder),
                    )
                )
        if self._unnamed_towns:
            candidate_sets.append(
                CandidateSet(towns=self._unnamed_towns, remainder=normalized_text, penalty=0)
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

    def _to_comparable_text(self, normalized_text: str, tier: MatchTier) -> str:
        match tier:
            case MatchTier.EXACT:
                return normalized_text
            case MatchTier.UNPREFIXED:
                return self.strip_prefix(normalized_text)
            case MatchTier.FOLDED:
                return self._normalizer.fold(self.strip_prefix(normalized_text))
