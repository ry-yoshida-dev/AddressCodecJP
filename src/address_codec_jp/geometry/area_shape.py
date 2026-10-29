import array
import json
from dataclasses import dataclass
from typing import ClassVar, Self

from address_codec_jp.geometry.coordinate_bounds import CoordinateBounds
from address_codec_jp.geometry.polygon import Polygon, Ring


@dataclass(frozen=True, slots=True)
class AreaShape:
    """
    Shape of an area as one or more polygons on JGD2011.

    Parameters
    ----------
    polygons : tuple[Polygon, ...]
        Parts of the area, such as its main land and enclaves or islands.

    Raises
    ------
    ValueError
        If there is no polygon.
    """

    _DECIMALS: ClassVar[int] = 7

    polygons: tuple[Polygon, ...]

    def __post_init__(self) -> None:
        if not self.polygons:
            raise ValueError("An area shape needs at least one polygon.")

    @classmethod
    def from_bytes(cls, data: bytes) -> Self:
        """
        Read a shape written by ``to_bytes``.

        Parameters
        ----------
        data : bytes
            Serialized shape.

        Returns
        -------
        Self
            Shape with the serialized polygons.

        Raises
        ------
        ValueError
            If the data is truncated or has trailing bytes.
        """
        if len(data) % 8:
            raise ValueError("Serialized area shape is truncated.")
        values = array.array("d")
        values.frombytes(data)
        cursor = 0

        def take(count: int) -> list[float]:
            nonlocal cursor
            if cursor + count > len(values):
                raise ValueError("Serialized area shape is truncated.")
            taken = values[cursor : cursor + count].tolist()
            cursor += count
            return taken

        polygons: list[Polygon] = []
        for _ in range(int(take(1)[0])):
            rings: list[Ring] = []
            for _ in range(int(take(1)[0])):
                flat = take(2 * int(take(1)[0]))
                rings.append(tuple(zip(flat[0::2], flat[1::2], strict=True)))
            polygons.append(Polygon(rings[0], tuple(rings[1:])))
        if cursor != len(values):
            raise ValueError("Serialized area shape has trailing data.")
        return cls(tuple(polygons))

    @property
    def bounds(self) -> CoordinateBounds:
        """
        Smallest box enclosing the shape.

        Returns
        -------
        CoordinateBounds
            Bounds of all polygons.
        """
        boxes = [polygon.bounds for polygon in self.polygons]
        return CoordinateBounds(
            south_degrees=min(box.south_degrees for box in boxes),
            north_degrees=max(box.north_degrees for box in boxes),
            west_degrees=min(box.west_degrees for box in boxes),
            east_degrees=max(box.east_degrees for box in boxes),
        )

    def contains(self, longitude_degrees: float, latitude_degrees: float) -> bool:
        """
        Tell whether a position lies inside the shape.

        Parameters
        ----------
        longitude_degrees : float
            Longitude on JGD2011.
        latitude_degrees : float
            Latitude on JGD2011.

        Returns
        -------
        bool
            ``True`` when a polygon contains the position.
        """
        return any(
            polygon.contains(longitude_degrees, latitude_degrees) for polygon in self.polygons
        )

    def merge(self, other: Self) -> Self:
        """
        Combine two shapes without dissolving shared boundaries.

        Parameters
        ----------
        other : Self
            Shape to add.

        Returns
        -------
        Self
            Shape with the polygons of both.
        """
        return type(self)((*self.polygons, *other.polygons))

    def to_bytes(self) -> bytes:
        """
        Serialize the shape for storage.

        Returns
        -------
        bytes
            Float64 values: the polygon count, then per polygon its ring count, and per
            ring its position count followed by the longitude and latitude pairs.
        """
        values: list[float] = [float(len(self.polygons))]
        for polygon in self.polygons:
            rings = (polygon.exterior, *polygon.holes)
            values.append(float(len(rings)))
            for ring in rings:
                values.append(float(len(ring)))
                values.extend(coordinate for position in ring for coordinate in position)
        return array.array("d", values).tobytes()

    def to_geojson(self) -> str:
        """
        Write the shape as a GeoJSON MultiPolygon geometry.

        Returns
        -------
        str
            Compact JSON of ``to_geojson_geometry``.
        """
        return json.dumps(self.to_geojson_geometry(), separators=(",", ":"))

    def to_geojson_geometry(self) -> dict[str, str | list[list[list[list[float]]]]]:
        """
        Build the shape as a GeoJSON MultiPolygon geometry object.

        Returns
        -------
        dict[str, str | list[list[list[list[float]]]]]
            ``type`` and ``coordinates`` with coordinates rounded to seven decimals,
            about a centimeter.
        """
        coordinates = [
            [self._write_ring(ring) for ring in (polygon.exterior, *polygon.holes)]
            for polygon in self.polygons
        ]
        return {"type": "MultiPolygon", "coordinates": coordinates}

    def _write_ring(self, ring: Ring) -> list[list[float]]:
        return [
            [round(longitude, self._DECIMALS), round(latitude, self._DECIMALS)]
            for longitude, latitude in ring
        ]
