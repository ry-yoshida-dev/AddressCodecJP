from enum import Enum, auto


class DataSource(Enum):
    """
    Published dataset that a response is derived from.

    Attributes
    ----------
    ADDRESS_BASE_REGISTRY
        Town master and representative points of the Address Base Registry, under the
        Public Data License 1.0.
    PARCEL_MASTER
        Land parcel master and parcel points of the Address Base Registry, which are
        derived from the registry office maps and fall under their terms of use.
    CENSUS_BOUNDARY
        Town polygons of the 2020 census boundaries, under the e-Stat terms of use.
    REGISTRY_MAP
        Land parcel polygons of the registry office maps, under their terms of use.
    """

    ADDRESS_BASE_REGISTRY = auto()
    PARCEL_MASTER = auto()
    CENSUS_BOUNDARY = auto()
    REGISTRY_MAP = auto()
