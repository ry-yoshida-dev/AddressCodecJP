from dataclasses import dataclass

from address_codec_jp.address import LotNumber


@dataclass(frozen=True, slots=True)
class LotParseResult:
    """
    Lot numbers parsed from the text following a town name.

    Parameters
    ----------
    lot : LotNumber
        Parsed block and residence numbers.
    remainder : str
        Text left after the lot numbers, such as a building name.
    """

    lot: LotNumber
    remainder: str
