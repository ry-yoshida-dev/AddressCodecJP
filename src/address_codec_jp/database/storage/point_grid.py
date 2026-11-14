import math
from typing import ClassVar

from address_codec_jp.geometry import CoordinateBounds


class PointGrid:
    """
    Grid of latitude and longitude cells that indexes stored points.

    A cell number orders cells row by row from south to north and west to east within a
    row, so the cells of one row inside a bounding box form one contiguous range. A
    bounding-box query then reads one index range per row instead of every point in
    the latitude band of the box.
    """

    CELL_DEGREES: ClassVar[float] = 0.01
    _ROW_STRIDE: ClassVar[int] = 100_000

    def cell_of(self, latitude: float, longitude: float) -> int:
        """
        Find the number of the cell that contains a point.

        Parameters
        ----------
        latitude : float
            Latitude in decimal degrees.
        longitude : float
            Longitude in decimal degrees, from -180 to 180.

        Returns
        -------
        int
            Cell number.
        """
        return self._row(latitude) * self._ROW_STRIDE + self._column(longitude)

    def row_ranges(self, bounds: CoordinateBounds) -> list[tuple[int, int]]:
        """
        List the cell ranges that cover a bounding box, one per row.

        Parameters
        ----------
        bounds : CoordinateBounds
            Search area.

        Returns
        -------
        list[tuple[int, int]]
            First and last cell number of each row, from south to north.
        """
        west = self._column(bounds.west_degrees)
        east = self._column(bounds.east_degrees)
        return [
            (row * self._ROW_STRIDE + west, row * self._ROW_STRIDE + east)
            for row in range(self._row(bounds.south_degrees), self._row(bounds.north_degrees) + 1)
        ]

    def _row(self, latitude: float) -> int:
        return math.floor(latitude / self.CELL_DEGREES)

    def _column(self, longitude: float) -> int:
        return math.floor((longitude + 180.0) / self.CELL_DEGREES)
