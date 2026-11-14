from enum import Enum, auto


class LotStyle(Enum):
    """
    Notation for chome and lot numbers.

    Attributes
    ----------
    AUTOMATIC
        The style of the numbering system of the lot numbers (``LotNumber.system``).
    RESIDENCE_INDICATION
        Residence indication style, e.g. ``1丁目2番3号`` or ``1丁目2番3-4号``.
    LAND_PARCEL
        Land parcel style, e.g. ``1丁目2番地3`` or ``124番地1の1``.
    HYPHEN
        Hyphenated style, e.g. ``1-2-3``.
    """

    AUTOMATIC = auto()
    RESIDENCE_INDICATION = auto()
    LAND_PARCEL = auto()
    HYPHEN = auto()
