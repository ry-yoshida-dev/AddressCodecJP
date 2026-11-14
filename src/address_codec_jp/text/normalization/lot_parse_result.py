from dataclasses import dataclass

from address_codec_jp.address import LotNumber, LotSystem


@dataclass(frozen=True, slots=True)
class LotParseResult:
    """
    Lot numbers parsed from the text following a town name.

    Parameters
    ----------
    lot : LotNumber
        Parsed lot numbers, in the system of ``notation`` or, without one, residence
        indication until the town tells otherwise.
    notation : LotSystem | None
        Numbering system the notation marks (``番地`` or ``番`` with ``号``), or ``None``
        when the notation fits both (``2-3``, ``2番3``).
    remainder : str
        Text left after the lot numbers, such as a building name.
    """

    lot: LotNumber
    notation: LotSystem | None
    remainder: str
