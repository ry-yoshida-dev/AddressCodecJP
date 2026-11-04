import re
from pathlib import Path
from typing import ClassVar

from address_codec_jp.datasets.boundaries.census_area import CensusArea
from address_codec_jp.datasets.boundaries.shapefile_reader import ShapefileReader
from address_codec_jp.errors import BoundaryFormatError
from address_codec_jp.geometry import AreaShape


class CensusBoundaryReader:
    """
    Reader of the town boundaries of the 2020 census (町丁・字等境界データ).

    Reads the shapefile of latitude and longitude on JGD2011 that e-Stat distributes.
    Every area is read, water areas and areas without a name included, so that together
    they cover the whole municipality; the polygons that share a census code, such as
    enclaves and islands, are combined into one area.
    """

    REQUIRED_FIELDS: ClassVar[tuple[str, ...]] = (
        "KEY_CODE",
        "HCODE",
        "PREF_NAME",
        "CITY_NAME",
        "S_NAME",
    )
    _TOWN_AREA_CODE: ClassVar[str] = "8101"
    _KEY_CODE_PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"[0-9]{5,}")

    def __init__(self) -> None:
        self._shapefile_reader: ShapefileReader = ShapefileReader()

    def read(self, path: Path) -> list[CensusArea]:
        """
        Read the areas of a boundary archive.

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
            If the archive is malformed, lacks a required field, or has a census code that
            does not start with the five-digit municipality code.
        """
        areas: dict[str, CensusArea] = {}
        for record in self._shapefile_reader.read(path):
            missing = [name for name in self.REQUIRED_FIELDS if name not in record.attributes]
            if missing:
                raise BoundaryFormatError(f"{path} lacks the fields {', '.join(missing)}.")
            attributes = record.attributes
            if not record.polygons:
                continue
            key_code = attributes["KEY_CODE"]
            if not self._KEY_CODE_PATTERN.fullmatch(key_code):
                raise BoundaryFormatError(f"{path} has a malformed KEY_CODE {key_code!r}.")
            shape = AreaShape(record.polygons)
            existing = areas.get(key_code)
            areas[key_code] = CensusArea(
                key_code=key_code,
                address=attributes["PREF_NAME"] + attributes["CITY_NAME"] + attributes["S_NAME"],
                town_name=attributes["S_NAME"],
                shape=shape if existing is None else existing.shape.merge(shape),
                is_land=attributes["HCODE"] == self._TOWN_AREA_CODE,
            )
        return list(areas.values())
