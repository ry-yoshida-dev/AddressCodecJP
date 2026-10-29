from enum import Enum


class AreaSource(Enum):
    """
    Published dataset an area shape is taken from.

    Attributes
    ----------
    CENSUS_BOUNDARY
        Town boundaries of the 2020 census (国勢調査 町丁・字等境界データ) on e-Stat.
    REGISTRY_MAP
        Land parcel maps of the registry offices (登記所備付地図データ) on the
        G-Spatial Information Center.
    """

    CENSUS_BOUNDARY = "census_boundary"
    REGISTRY_MAP = "registry_map"
