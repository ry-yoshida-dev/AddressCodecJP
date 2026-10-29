from enum import Enum, auto


class AddressLevel(Enum):
    """
    Granularity of an address code.

    Attributes
    ----------
    PREFECTURE
        Prefecture only, e.g. ``東京都``.
    MUNICIPALITY
        Municipality, e.g. ``東京都台東区``.
    TOWN
        Town (oaza, chome, or koaza), optionally with lot numbers.
    """

    PREFECTURE = auto()
    MUNICIPALITY = auto()
    TOWN = auto()
