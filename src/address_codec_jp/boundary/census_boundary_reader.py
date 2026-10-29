from pathlib import Path
from typing import ClassVar

from address_codec_jp.boundary.census_area import CensusArea
from address_codec_jp.boundary.shapefile_reader import ShapefileReader
from address_codec_jp.domain.area_shape import AreaShape
from address_codec_jp.errors.boundary_format_error import BoundaryFormatError


class CensusBoundaryReader:
    """
    Reader of the town boundaries of the 2020 census (町丁・字等境界データ).

    Reads the shapefile of latitude and longitude on JGD2011 that e-Stat distributes.
    Water areas and areas without a name are skipped, and the polygons that share a
    census code, such as enclaves and islands, are combined into one area.
    """

    REQUIRED_FIELDS: ClassVar[tuple[str, ...]] = (
        "KEY_CODE",
        "HCODE",
        "PREF_NAME",
        "CITY_NAME",
        "S_NAME",
    )
    _TOWN_AREA_CODE: ClassVar[str] = "8101"

    def __init__(self) -> None:
        self._shapefile_reader: ShapefileReader = ShapefileReader()

    def read(self, path: Path) -> list[CensusArea]:
        """
        Read the named land areas of a boundary archive.

        Parameters
        ----------
        path : Path
            ZIP archive downloaded from e-Stat.

        Returns
        -------
        list[CensusArea]
            Areas in the order of their first polygon.

        Raises
        ------
        BoundaryFormatError
            If the archive is malformed or lacks a required field.
        """
        areas: dict[str, CensusArea] = {}
        for record in self._shapefile_reader.read(path):
            missing = [name for name in self.REQUIRED_FIELDS if name not in record.attributes]
            if missing:
                raise BoundaryFormatError(f"{path} lacks the fields {', '.join(missing)}.")
            attributes = record.attributes
            if attributes["HCODE"] != self._TOWN_AREA_CODE or not attributes["S_NAME"]:
                continue
            if not record.polygons:
                continue
            key_code = attributes["KEY_CODE"]
            shape = AreaShape(record.polygons)
            existing = areas.get(key_code)
            areas[key_code] = CensusArea(
                key_code=key_code,
                address=attributes["PREF_NAME"] + attributes["CITY_NAME"] + attributes["S_NAME"],
                shape=shape if existing is None else existing.shape.merge(shape),
            )
        return list(areas.values())
