from dataclasses import dataclass

from address_codec_jp.address import LotSystem
from address_codec_jp.geometry.representative_point import RepresentativePoint


@dataclass(frozen=True, slots=True)
class TownPosition:
    """
    Representative point of a town and the numbering of its lots.

    Parameters
    ----------
    lg_code : str
        Six-digit local government code.
    machiaza_id : str
        Seven-digit town identifier.
    lot_system : LotSystem
        Numbering system of the lot numbers in the town.
    point : RepresentativePoint
        Published representative point.
    """

    lg_code: str
    machiaza_id: str
    lot_system: LotSystem
    point: RepresentativePoint
