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
