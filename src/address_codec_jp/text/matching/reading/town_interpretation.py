from dataclasses import dataclass

from address_codec_jp.address import LotNumber, LotSystem, Town
from address_codec_jp.results import MatchTier


@dataclass(frozen=True, slots=True)
class TownInterpretation:
    """
    One complete reading of the text after a municipality.

    Parameters
    ----------
    towns : list[Town]
        Towns consistent with the reading. More than one town means the reading is ambiguous.
    lot : LotNumber
        Lot numbers parsed after the town name, in the system of ``lot_notation`` or,
        without one, residence indication.
    lot_notation : LotSystem | None
        Numbering system the lot notation marks, or ``None`` when it fits both.
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
    lot_notation: LotSystem | None
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

    def lot_for(self, town: Town) -> LotNumber:
        """
        Read the lot numbers in the numbering system of a town.

        A town with one numbering system decides it, because addresses are often written
        loosely (``2番地3`` for residence indication). Where both systems are used, the
        notation decides, and residence indication is assumed when it fits both.

        Parameters
        ----------
        town : Town
            Town the lot numbers belong to.

        Returns
        -------
        LotNumber
            Lot numbers in the numbering system of ``town``.
        """
        if len(town.lot_systems) == 1:
            return self.lot.with_system(next(iter(town.lot_systems)))
        return self.lot.with_system(self.lot_notation or LotSystem.RESIDENCE_INDICATION)
