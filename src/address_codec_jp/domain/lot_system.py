from __future__ import annotations

from enum import Enum


class LotSystem(Enum):
    """
    Numbering system of the lot numbers in a town.

    Attributes
    ----------
    RESIDENCE_INDICATION
        Residence indication (住居表示): ``番`` is a block and ``号`` a residence.
    LAND_PARCEL
        Land parcel numbers (地番): ``番地`` is a parcel and the branch its sub-parcel.
    """

    RESIDENCE_INDICATION = "residence_indication"
    LAND_PARCEL = "land_parcel"

    @classmethod
    def from_residence_indication_flag(cls, flag: str) -> LotSystem:
        """
        Read the residence indication flag (``rsdt_addr_flg``) of the registry.

        Parameters
        ----------
        flag : str
            ``1`` for residence indication, ``0`` for land parcel numbers.

        Returns
        -------
        LotSystem
            Numbering system the flag stands for.

        Raises
        ------
        ValueError
            If the flag is neither ``0`` nor ``1``.
        """
        match flag:
            case "1":
                return cls.RESIDENCE_INDICATION
            case "0":
                return cls.LAND_PARCEL
            case _:
                raise ValueError(f"rsdt_addr_flg must be 0 or 1, got {flag!r}.")
