import itertools
import struct
import zipfile
import zlib
from collections.abc import Iterator
from pathlib import Path
from typing import ClassVar

import numpy as np
import numpy.typing as npt

from address_codec_jp.datasets.boundaries.shapefile_record import ShapefileRecord
from address_codec_jp.errors import BoundaryFormatError
from address_codec_jp.geometry import Polygon, Ring


class ShapefileReader:
    """
    Reader of a polygon shapefile packed in a ZIP archive.

    The archive must hold one ``.shp`` file and one ``.dbf`` file. Rings running
    clockwise are exteriors, and the others are holes of the exterior that contains
    them, as the shapefile specification prescribes, also when a hole touches its
    exterior.

    Parameters
    ----------
    encoding : str
        Text encoding of the attribute table.
    """

    _NULL_SHAPE: ClassVar[int] = 0
    _POLYGON_SHAPE: ClassVar[int] = 5
    _FILE_HEADER_SIZE: ClassVar[int] = 100
    _DELETED_FLAG: ClassVar[int] = 0x2A
    _FIELD_TERMINATOR: ClassVar[int] = 0x0D
    _BOUNDARY_TOLERANCE: ClassVar[float] = 1e-9

    def __init__(self, encoding: str = "cp932") -> None:
        self._encoding: str = encoding

    def read(self, path: Path) -> list[ShapefileRecord]:
        """
        Read all features of the archive.

        Parameters
        ----------
        path : Path
            ZIP archive of the shapefile.

        Returns
        -------
        list[ShapefileRecord]
            Features in file order.

        Raises
        ------
        BoundaryFormatError
            If the archive lacks a file or is broken, or a file is malformed, such as
            truncated or with attributes not in the encoding.
        """
        try:
            with zipfile.ZipFile(path) as archive:
                shapes = archive.read(self._member(archive, ".shp", path))
                table = archive.read(self._member(archive, ".dbf", path))
        except (zipfile.BadZipFile, zlib.error, EOFError) as error:
            raise BoundaryFormatError(
                f"{path} is not a valid shapefile archive: {error}"
            ) from error
        try:
            polygons = list(self._read_shapes(shapes, path))
            attributes = list(self._read_table(table, path))
        except (struct.error, UnicodeDecodeError) as error:
            raise BoundaryFormatError(f"{path} has a malformed shapefile: {error}") from error
        if len(polygons) != len(attributes):
            raise BoundaryFormatError(
                f"{path} has {len(polygons)} shapes but {len(attributes)} attribute rows."
            )
        return [
            ShapefileRecord(attributes=row, polygons=shape)
            for row, shape in zip(attributes, polygons, strict=True)
        ]

    def _member(self, archive: zipfile.ZipFile, suffix: str, path: Path) -> str:
        names = [name for name in archive.namelist() if name.lower().endswith(suffix)]
        if len(names) != 1:
            raise BoundaryFormatError(f"{path} must hold one {suffix} file, found {len(names)}.")
        return names[0]

    def _read_shapes(self, data: bytes, path: Path) -> Iterator[tuple[Polygon, ...]]:
        offset = self._FILE_HEADER_SIZE
        while offset < len(data):
            if offset + 12 > len(data):
                raise BoundaryFormatError(f"{path} ends inside a record header.")
            content_words: int = struct.unpack_from(">i", data, offset + 4)[0]
            content_start = offset + 8
            offset = content_start + 2 * content_words
            if offset > len(data):
                raise BoundaryFormatError(f"{path} ends inside a record.")
            shape_type: int = struct.unpack_from("<i", data, content_start)[0]
            match shape_type:
                case self._NULL_SHAPE:
                    yield ()
                case self._POLYGON_SHAPE:
                    yield self._read_polygon(data, content_start)
                case _:
                    raise BoundaryFormatError(f"{path} has unsupported shape type {shape_type}.")

    def _read_polygon(self, data: bytes, start: int) -> tuple[Polygon, ...]:
        part_count, point_count = struct.unpack_from("<2i", data, start + 36)
        parts_start = start + 44
        points_start = parts_start + 4 * part_count
        part_starts = [*struct.unpack_from(f"<{part_count}i", data, parts_start), point_count]
        coordinates = struct.unpack_from(f"<{2 * point_count}d", data, points_start)
        rings: list[Ring] = [
            Polygon.close(
                [
                    (coordinates[2 * index], coordinates[2 * index + 1])
                    for index in range(part_starts[part], part_starts[part + 1])
                ]
            )
            for part in range(part_count)
        ]
        return self._assemble([ring for ring in rings if len(ring) >= 4])

    def _assemble(self, rings: list[Ring]) -> tuple[Polygon, ...]:
        exteriors = [ring for ring in rings if Polygon.is_clockwise(ring)]
        holes_of: dict[int, list[Ring]] = {index: [] for index in range(len(exteriors))}
        for ring in rings:
            if Polygon.is_clockwise(ring):
                continue
            container = next(
                (
                    index
                    for index, exterior in enumerate(exteriors)
                    if self._encloses(exterior, ring)
                ),
                None,
            )
            if container is None:
                exteriors.append(ring)
                holes_of[len(exteriors) - 1] = []
            else:
                holes_of[container].append(ring)
        return tuple(
            Polygon(exterior, tuple(holes_of[index])) for index, exterior in enumerate(exteriors)
        )

    def _encloses(self, exterior: Ring, ring: Ring) -> bool:
        # A hole may touch its exterior, and a position on the exterior's boundary can
        # fall either side of the containment test, so the hole is judged by its first
        # vertex or edge midpoint off that boundary. A ring lying wholly on the boundary
        # is taken as enclosed.
        segments: npt.NDArray[np.float64] = np.asarray(exterior, dtype=np.float64)
        starts = segments[:-1]
        directions = segments[1:] - starts
        lengths = np.hypot(directions[:, 0], directions[:, 1])
        midpoints = [
            ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
            for start, end in itertools.pairwise(ring)
        ]
        polygon = Polygon(exterior)
        for longitude, latitude in [*ring[:-1], *midpoints]:
            offset_longitudes = longitude - starts[:, 0]
            offset_latitudes = latitude - starts[:, 1]
            cross = directions[:, 0] * offset_latitudes - directions[:, 1] * offset_longitudes
            projection = directions[:, 0] * offset_longitudes + directions[:, 1] * offset_latitudes
            is_on_boundary = bool(
                np.any(
                    (lengths > 0)
                    & (np.abs(cross) <= self._BOUNDARY_TOLERANCE * lengths)
                    & (projection >= -self._BOUNDARY_TOLERANCE * lengths)
                    & (projection <= lengths * (lengths + self._BOUNDARY_TOLERANCE))
                )
            )
            if not is_on_boundary:
                return polygon.contains(longitude, latitude)
        return True

    def _read_table(self, data: bytes, path: Path) -> Iterator[dict[str, str]]:
        if len(data) < 32:
            raise BoundaryFormatError(f"{path} has a truncated attribute table.")
        record_count, header_size, record_size = struct.unpack_from("<IHH", data, 4)
        fields: list[tuple[str, int]] = []
        position = 32
        while position < header_size and data[position] != self._FIELD_TERMINATOR:
            name = data[position : position + 11].split(b"\0", 1)[0].decode("ascii")
            fields.append((name, data[position + 16]))
            position += 32
        for index in range(record_count):
            start = header_size + index * record_size
            record = data[start : start + record_size]
            if len(record) < record_size:
                raise BoundaryFormatError(f"{path} has a truncated attribute row.")
            if record[0] == self._DELETED_FLAG:
                continue
            values: dict[str, str] = {}
            cursor = 1
            for name, length in fields:
                values[name] = record[cursor : cursor + length].decode(self._encoding).strip()
                cursor += length
            yield values
