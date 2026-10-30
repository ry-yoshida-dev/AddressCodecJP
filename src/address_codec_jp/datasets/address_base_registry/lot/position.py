from dataclasses import dataclass

from address_codec_jp.address import LotSystem
from address_codec_jp.geometry import RepresentativePoint


@dataclass(frozen=True, slots=True)
class LotPosition:
    """
    Representative point of a block, residence, or parcel.

    Parameters
    ----------
    lg_code : str
        Six-digit local government code.
    machiaza_id : str
        Seven-digit town identifier.
    lot_system : LotSystem
        Numbering system the identifier belongs to.
    lot_id : str
        Identifier unique within the town and numbering system.
    point : RepresentativePoint
        Published representative point.
    """

    lg_code: str
    machiaza_id: str
    lot_system: LotSystem
    lot_id: str
    point: RepresentativePoint
