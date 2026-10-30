from dataclasses import dataclass

from address_codec_jp.address import LotNumber, LotSystem


@dataclass(frozen=True, slots=True)
class LotEntry:
    """
    Registry identifier of a block, residence, or parcel and its lot numbers.

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
    lot : LotNumber
        Block and residence numbers, or parcel and sub-parcel numbers.
    """

    lg_code: str
    machiaza_id: str
    lot_system: LotSystem
    lot_id: str
    lot: LotNumber
