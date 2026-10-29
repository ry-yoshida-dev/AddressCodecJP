from __future__ import annotations

from enum import Enum, auto

from address_codec_jp.domain.address_code import AddressCode
from address_codec_jp.domain.address_level import AddressLevel


class PositionLevel(Enum):
    """
    Granularity of the area a representative point stands for.

    Attributes
    ----------
    PREFECTURE
        Prefecture.
    MUNICIPALITY
        Municipality.
    TOWN
        Town (oaza, chome, or koaza).
    BLOCK
        Block (``番``) of a residence indication, or a parcel (``番地``).
    RESIDENCE
        Residence (``号``) of a residence indication, or a sub-parcel (``番地の4``).
    """

    PREFECTURE = auto()
    MUNICIPALITY = auto()
    TOWN = auto()
    BLOCK = auto()
    RESIDENCE = auto()

    @classmethod
    def of(cls, code: AddressCode) -> PositionLevel:
        """
        Granularity of an address code.

        Parameters
        ----------
        code : AddressCode
            Address code.

        Returns
        -------
        PositionLevel
            Level of the most specific component of the code.
        """
        match code.level, len(code.lot.numbers):
            case AddressLevel.PREFECTURE, _:
                return cls.PREFECTURE
            case AddressLevel.MUNICIPALITY, _:
                return cls.MUNICIPALITY
            case AddressLevel.TOWN, 0:
                return cls.TOWN
            case AddressLevel.TOWN, 1:
                return cls.BLOCK
            case AddressLevel.TOWN, _:
                return cls.RESIDENCE
