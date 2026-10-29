import re
from typing import ClassVar

from geo_coordinate import GeoCoordinate


class CoordinateText:
    """Parser of coordinates written as ``latitude,longitude`` in decimal degrees."""

    _PATTERN: ClassVar[re.Pattern[str]] = re.compile(
        r"\s*(?P<latitude>[-+]?[0-9]+(?:\.[0-9]+)?)\s*,\s*(?P<longitude>[-+]?[0-9]+(?:\.[0-9]+)?)\s*"
    )

    def parse(self, text: str) -> GeoCoordinate:
        """
        Parse a coordinate.

        Parameters
        ----------
        text : str
            Text such as ``35.6812,139.7671``.

        Returns
        -------
        GeoCoordinate
            Parsed coordinate.

        Raises
        ------
        ValueError
            If the text is not two comma-separated decimal numbers, or a value is out
            of range.
        """
        matched = self._PATTERN.fullmatch(text)
        if matched is None:
            raise ValueError(f"Coordinate must be 'latitude,longitude', got {text!r}.")
        latitude = float(matched.group("latitude"))
        longitude = float(matched.group("longitude"))
        if not -90.0 <= latitude <= 90.0 or not -180.0 <= longitude <= 180.0:
            raise ValueError(f"Coordinate {text!r} is out of range.")
        return GeoCoordinate.from_degrees(latitude, longitude)
