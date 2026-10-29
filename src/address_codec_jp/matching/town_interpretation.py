from dataclasses import dataclass

from address_codec_jp.domain.lot_number import LotNumber
from address_codec_jp.domain.match_tier import MatchTier
from address_codec_jp.domain.town import Town


@dataclass(frozen=True, slots=True)
class TownInterpretation:
    """
    One complete reading of the text after a municipality.

    Parameters
    ----------
    towns : list[Town]
        Towns consistent with the reading. More than one town means the reading is ambiguous.
    lot : LotNumber
        Lot numbers parsed after the town name.
    remainder : str
        Text left after the lot numbers.
    name_length : int
        Number of characters consumed by oaza, chome, and koaza names.
    penalty : int
        Accumulated ``MatchTier.penalty`` of the name comparisons.
    loosest_tier : MatchTier
        Loosest tier of the name comparisons.
    """

    towns: list[Town]
    lot: LotNumber
    remainder: str
    name_length: int
    penalty: int
    loosest_tier: MatchTier

    @property
    def ranking_key(self) -> tuple[int, int, int]:
        """
        Sort key; smaller is better.

        Readings that leave less unparsed text win, then readings that explain more of
        the text by registered names, then readings that use stricter comparisons.

        Returns
        -------
        tuple[int, int, int]
            Remainder length, negated name length, and penalty.
        """
        return (len(self.remainder), -self.name_length, self.penalty)
