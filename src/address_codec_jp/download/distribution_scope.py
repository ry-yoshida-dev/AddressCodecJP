from enum import Enum, auto


class DistributionScope(Enum):
    """
    Area unit in which the registry distributes a dataset.

    Attributes
    ----------
    NATIONWIDE
        One file for the whole country.
    PREFECTURE
        One file per prefecture, named by the two-digit prefecture code.
    MUNICIPALITY
        One file per municipality, named by the six-digit local government code.
    """

    NATIONWIDE = auto()
    PREFECTURE = auto()
    MUNICIPALITY = auto()
