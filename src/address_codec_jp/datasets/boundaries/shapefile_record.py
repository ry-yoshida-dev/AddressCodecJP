from dataclasses import dataclass

from address_codec_jp.geometry import Polygon


@dataclass(frozen=True, slots=True)
class ShapefileRecord:
    """
    One feature of a polygon shapefile.

    Parameters
    ----------
    attributes : dict[str, str]
        Attribute values by field name, with surrounding blanks removed.
    polygons : tuple[Polygon, ...]
        Polygons of the feature, empty for a null shape.
    """

    attributes: dict[str, str]
    polygons: tuple[Polygon, ...]
