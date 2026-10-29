from dataclasses import dataclass

from address_codec_jp.address import LotSystem


@dataclass(frozen=True, slots=True)
class LotRemoval:
    """
    Block, residence, or parcel that a number master marks as abolished.

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
    """

    lg_code: str
    machiaza_id: str
    lot_system: LotSystem
    lot_id: str
