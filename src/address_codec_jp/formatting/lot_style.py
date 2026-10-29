from enum import Enum, auto


class LotStyle(Enum):
    """
    Notation for chome and lot numbers.

    Attributes
    ----------
    RESIDENCE_INDICATION
        Residence indication style, e.g. ``1丁目2番3号``.
    LAND_PARCEL
        Land parcel style, e.g. ``1丁目2番地3``.
    HYPHEN
        Hyphenated style, e.g. ``1-2-3``.
    """

    RESIDENCE_INDICATION = auto()
    LAND_PARCEL = auto()
    HYPHEN = auto()
