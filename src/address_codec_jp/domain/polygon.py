from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from address_codec_jp.domain.coordinate_bounds import CoordinateBounds

type Ring = tuple[tuple[float, float], ...]


@dataclass(frozen=True, slots=True)
class Polygon:
    """
    Polygon of longitude and latitude pairs in decimal degrees.

    Parameters
    ----------
    exterior : Ring
        Closed outer boundary as ``(longitude, latitude)`` pairs, the first pair repeated
        at the end.
    holes : tuple[Ring, ...]
        Closed inner boundaries.

    Raises
    ------
    ValueError
        If a ring has fewer than four pairs or is not closed.
    """

    exterior: Ring
    holes: tuple[Ring, ...] = ()

    def __post_init__(self) -> None:
        for ring in (self.exterior, *self.holes):
            if len(ring) < 4:
                raise ValueError(f"A ring needs at least four positions, got {len(ring)}.")
            if ring[0] != ring[-1]:
                raise ValueError("A ring must end at its first position.")

    @property
    def bounds(self) -> CoordinateBounds:
        """
        Smallest box enclosing the polygon.

        Returns
        -------
        CoordinateBounds
            Bounds of the exterior.
        """
        positions = np.asarray(self.exterior, dtype=np.float64)
        return CoordinateBounds(
            south_degrees=float(positions[:, 1].min()),
            north_degrees=float(positions[:, 1].max()),
            west_degrees=float(positions[:, 0].min()),
            east_degrees=float(positions[:, 0].max()),
        )

    def contains(self, longitude_degrees: float, latitude_degrees: float) -> bool:
        """
        Tell whether a position lies inside the polygon.

        Parameters
        ----------
        longitude_degrees : float
            Longitude of the position.
        latitude_degrees : float
            Latitude of the position.

        Returns
        -------
        bool
            ``True`` when the position is inside the exterior and outside every hole.
        """
        if not self._is_in_ring(self.exterior, longitude_degrees, latitude_degrees):
            return False
        return not any(
            self._is_in_ring(hole, longitude_degrees, latitude_degrees) for hole in self.holes
        )

    @staticmethod
    def is_clockwise(ring: Ring) -> bool:
        """
        Tell whether a ring runs clockwise with longitude to the right and latitude up.

        Parameters
        ----------
        ring : Ring
            Closed ring.

        Returns
        -------
        bool
            ``True`` for a negative signed area.
        """
        positions = np.asarray(ring, dtype=np.float64)
        longitudes = positions[:, 0]
        latitudes = positions[:, 1]
        signed_double_area = float(
            np.sum(longitudes[:-1] * latitudes[1:] - longitudes[1:] * latitudes[:-1])
        )
        return signed_double_area < 0

    @staticmethod
    def close(positions: list[tuple[float, float]]) -> Ring:
        """
        Close a sequence of positions into a ring.

        Parameters
        ----------
        positions : list[tuple[float, float]]
            Positions of the boundary, closed or not.

        Returns
        -------
        Ring
            Positions with the first one repeated at the end when missing.
        """
        if positions and positions[0] != positions[-1]:
            return (*positions, positions[0])
        return tuple(positions)

    def _is_in_ring(self, ring: Ring, longitude_degrees: float, latitude_degrees: float) -> bool:
        positions: npt.NDArray[np.float64] = np.asarray(ring, dtype=np.float64)
        start_longitudes = positions[:-1, 0]
        start_latitudes = positions[:-1, 1]
        end_longitudes = positions[1:, 0]
        end_latitudes = positions[1:, 1]
        is_straddling: npt.NDArray[np.bool_] = np.not_equal(
            np.greater(start_latitudes, latitude_degrees),
            np.greater(end_latitudes, latitude_degrees),
        )
        with np.errstate(divide="ignore", invalid="ignore"):
            crossing_longitudes = start_longitudes + (latitude_degrees - start_latitudes) * (
                end_longitudes - start_longitudes
            ) / (end_latitudes - start_latitudes)
        is_crossed: npt.NDArray[np.bool_] = np.logical_and(
            is_straddling, np.less(longitude_degrees, crossing_longitudes)
        )
        crossings = int(np.count_nonzero(is_crossed))
        return crossings % 2 == 1
