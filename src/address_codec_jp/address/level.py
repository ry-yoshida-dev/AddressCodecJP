from enum import Enum, auto


class AddressLevel(Enum):
    """
    Granularity of an address code, from the widest to the narrowest area.

    Attributes
    ----------
    PREFECTURE
        Prefecture only, e.g. ``東京都``.
    MUNICIPALITY
        Municipality, e.g. ``東京都台東区``.
    TOWN
        Town (oaza, chome, or koaza) without lot numbers.
    BLOCK
        Block (``番``) of a residence indication, or a parcel (``番地``).
    RESIDENCE
        Residence (``号``) of a residence indication or its branch (``3-4号``), or a
        branch of a parcel (``番地の4``, ``番地1の1``).
    """

    PREFECTURE = auto()
    MUNICIPALITY = auto()
    TOWN = auto()
    BLOCK = auto()
    RESIDENCE = auto()
