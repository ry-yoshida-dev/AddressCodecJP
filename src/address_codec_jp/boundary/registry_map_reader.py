import array
import io
import re
import unicodedata
import xml.etree.ElementTree as ElementTree
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import ClassVar

import numpy as np
import numpy.typing as npt
from geo_coordinate import JapanPlaneRectangularZone, PlaneCoordinates, PlaneProjection

from address_codec_jp.boundary.registry_map_parcel import RegistryMapParcel
from address_codec_jp.domain.area_shape import AreaShape
from address_codec_jp.domain.polygon import Polygon, Ring
from address_codec_jp.errors.boundary_format_error import BoundaryFormatError

type PlanePosition = tuple[float, float]


class RegistryMapReader:
    """
    Reader of the land parcel maps of the registry offices (登記所備付地図データ).

    An archive from the G-Spatial Information Center holds one ZIP archive per map
    sheet, each with one map XML file. Sheets on an arbitrary local coordinate system
    (任意座標系) cannot be placed on the earth and are skipped; sheets on a zone of the
    plane rectangular coordinate system (公共座標) are projected to JGD2011.
    """

    _MAP_NAMESPACE: ClassVar[str] = "{http://www.moj.go.jp/MINJI/tizuxml}"
    _GEOMETRY_NAMESPACE: ClassVar[str] = "{http://www.moj.go.jp/MINJI/tizuzumen}"
    _ZONE_PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"公共座標(\d+)系")

    def read(self, path: Path) -> list[RegistryMapParcel]:
        """
        Read the placeable parcels of an archive.

        Parameters
        ----------
        path : Path
            ZIP archive of map sheets, or one map XML file.

        Returns
        -------
        list[RegistryMapParcel]
            Parcels of the sheets on public coordinates.

        Raises
        ------
        BoundaryFormatError
            If a map file is malformed.
        """
        if path.suffix.lower() == ".xml":
            return self._read_map(path.read_bytes(), path.name)
        with zipfile.ZipFile(path) as archive:
            return [
                parcel
                for name, data in self._iterate_maps(archive)
                for parcel in self._read_map(data, name)
            ]

    def _iterate_maps(self, archive: zipfile.ZipFile) -> Iterator[tuple[str, bytes]]:
        for name in sorted(archive.namelist()):
            lowered = name.lower()
            if lowered.endswith(".xml"):
                yield name, archive.read(name)
            elif lowered.endswith(".zip"):
                with zipfile.ZipFile(io.BytesIO(archive.read(name))) as inner:
                    yield from self._iterate_maps(inner)

    def _read_map(self, data: bytes, name: str) -> list[RegistryMapParcel]:
        try:
            root = ElementTree.fromstring(data)
        except ElementTree.ParseError as error:
            raise BoundaryFormatError(f"{name} is not a well-formed map XML file.") from error
        zone = self._zone(self._text(root, "座標系"))
        if zone is None:
            return []
        municipality_name = self._text(root, "市区町村名")
        geometry = root.find(f"{self._MAP_NAMESPACE}空間属性")
        subjects = root.find(f"{self._MAP_NAMESPACE}主題属性")
        if geometry is None or subjects is None:
            raise BoundaryFormatError(f"{name} lacks the geometry or subject section.")
        points = self._read_points(geometry)
        surfaces = self._read_surfaces(geometry, self._read_curves(geometry, points))
        placed: list[tuple[ElementTree.Element, list[list[PlanePosition]]]] = []
        for parcel in subjects.iter(f"{self._MAP_NAMESPACE}筆"):
            shape_reference = parcel.find(f"{self._MAP_NAMESPACE}形状")
            if shape_reference is not None and shape_reference.get("idref", "") in surfaces:
                placed.append((parcel, surfaces[shape_reference.get("idref", "")]))
        rings = self._project([ring for _, surface in placed for ring in surface], zone)
        result: list[RegistryMapParcel] = []
        cursor = 0
        for parcel, surface in placed:
            surface_rings = rings[cursor : cursor + len(surface)]
            cursor += len(surface)
            if any(len(ring) < 4 for ring in surface_rings):
                continue
            result.append(
                RegistryMapParcel(
                    municipality_name=municipality_name,
                    oaza_name=self._child_text(parcel, "大字名"),
                    chome_name=self._child_text(parcel, "丁目名"),
                    lot_text=self._child_text(parcel, "地番"),
                    shape=AreaShape((Polygon(surface_rings[0], tuple(surface_rings[1:])),)),
                )
            )
        return result

    def _zone(self, coordinate_system: str) -> JapanPlaneRectangularZone | None:
        match_result = self._ZONE_PATTERN.fullmatch(
            unicodedata.normalize("NFKC", coordinate_system)
        )
        if match_result is None:
            return None
        return JapanPlaneRectangularZone.from_number(int(match_result.group(1)))

    def _read_points(self, geometry: ElementTree.Element) -> dict[str, PlanePosition]:
        points: dict[str, PlanePosition] = {}
        for point in geometry.iter(f"{self._GEOMETRY_NAMESPACE}GM_Point"):
            position = point.find(f".//{self._GEOMETRY_NAMESPACE}DirectPosition")
            if position is not None:
                points[point.get("id", "")] = self._position(position)
        return points

    def _read_curves(
        self, geometry: ElementTree.Element, points: dict[str, PlanePosition]
    ) -> dict[str, list[PlanePosition]]:
        curves: dict[str, list[PlanePosition]] = {}
        for curve in geometry.iter(f"{self._GEOMETRY_NAMESPACE}GM_Curve"):
            positions: list[PlanePosition] = []
            for column in curve.iter(f"{self._GEOMETRY_NAMESPACE}GM_PointArray.column"):
                direct = column.find(f"{self._GEOMETRY_NAMESPACE}GM_Position.direct")
                reference = column.find(f".//{self._GEOMETRY_NAMESPACE}GM_PointRef.point")
                if direct is not None:
                    positions.append(self._position(direct))
                elif reference is not None and reference.get("idref", "") in points:
                    positions.append(points[reference.get("idref", "")])
            curves[curve.get("id", "")] = positions
        return curves

    def _read_surfaces(
        self, geometry: ElementTree.Element, curves: dict[str, list[PlanePosition]]
    ) -> dict[str, list[list[PlanePosition]]]:
        surfaces: dict[str, list[list[PlanePosition]]] = {}
        for surface in geometry.iter(f"{self._GEOMETRY_NAMESPACE}GM_Surface"):
            rings: list[list[PlanePosition]] = []
            for boundary_name in ("GM_SurfaceBoundary.exterior", "GM_SurfaceBoundary.interior"):
                for boundary in surface.iter(f"{self._GEOMETRY_NAMESPACE}{boundary_name}"):
                    rings.extend(
                        self._chain(ring, curves)
                        for ring in boundary.iter(f"{self._GEOMETRY_NAMESPACE}GM_Ring")
                    )
            if rings:
                surfaces[surface.get("id", "")] = rings
        return surfaces

    def _chain(
        self, ring: ElementTree.Element, curves: dict[str, list[PlanePosition]]
    ) -> list[PlanePosition]:
        chained: list[PlanePosition] = []
        for generator in ring.iter(f"{self._GEOMETRY_NAMESPACE}GM_CompositeCurve.generator"):
            positions = curves.get(generator.get("idref", ""), [])
            if not positions:
                continue
            if not chained:
                chained.extend(positions)
            elif positions[0] == chained[-1]:
                chained.extend(positions[1:])
            elif positions[-1] == chained[-1]:
                chained.extend(reversed(positions[:-1]))
            else:
                chained.extend(positions)
        if chained and chained[0] != chained[-1]:
            chained.append(chained[0])
        return chained

    def _project(
        self, plane_rings: list[list[PlanePosition]], zone: JapanPlaneRectangularZone
    ) -> list[Ring]:
        flat = [position for ring in plane_rings for position in ring]
        if not flat:
            return [() for _ in plane_rings]
        northing_easting = np.asarray(flat, dtype=np.float64)
        plane = PlaneCoordinates.from_points(northing_easting[:, ::-1].copy(), zone)
        geographic = PlaneProjection(zone).unproject(plane)
        longitudes = self._to_floats(geographic.longitude.degree)
        latitudes = self._to_floats(geographic.latitude.degree)
        rings: list[Ring] = []
        cursor = 0
        for ring in plane_rings:
            rings.append(
                tuple(
                    zip(
                        longitudes[cursor : cursor + len(ring)],
                        latitudes[cursor : cursor + len(ring)],
                        strict=True,
                    )
                )
            )
            cursor += len(ring)
        return rings

    def _to_floats(self, values: npt.NDArray[np.integer | np.floating]) -> list[float]:
        converted = array.array("d")
        converted.frombytes(np.ascontiguousarray(values, dtype=np.float64).tobytes())
        return converted.tolist()

    def _position(self, element: ElementTree.Element) -> PlanePosition:
        return (
            float(self._child_text(element, "X", self._GEOMETRY_NAMESPACE)),
            float(self._child_text(element, "Y", self._GEOMETRY_NAMESPACE)),
        )

    def _text(self, root: ElementTree.Element, name: str) -> str:
        return self._child_text(root, name)

    def _child_text(
        self, element: ElementTree.Element, name: str, namespace: str = _MAP_NAMESPACE
    ) -> str:
        child = element.find(f"{namespace}{name}")
        if child is None or child.text is None:
            return ""
        return child.text.strip()
