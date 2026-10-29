from dataclasses import dataclass

from address_codec_jp.domain.lot_number import LotNumber
from address_codec_jp.domain.municipality import Municipality
from address_codec_jp.domain.prefecture import Prefecture
from address_codec_jp.domain.town import Town


@dataclass(frozen=True, slots=True)
class AreaMatch:
    """
    Most specific registered area identified at the start of a normalized address.

    Parameters
    ----------
    prefecture : Prefecture
        Matched prefecture.
    municipality : Municipality | None
        Matched municipality. ``None`` when the address ends at the prefecture.
    town : Town | None
        Matched town. ``None`` when the address ends at the prefecture or municipality.
    lot : LotNumber
        Lot numbers after the town name. Empty unless a town is matched.
    remainder : str
        Normalized text following the matched area and lot numbers.
    """

    prefecture: Prefecture
    municipality: Municipality | None
    town: Town | None
    lot: LotNumber
    remainder: str
