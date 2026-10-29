from geo_coordinate import DatumTransformation, GeoCoordinate, GeodeticCrs

from address_codec_jp.domain.representative_point import RepresentativePoint


class DatumConverter:
    """
    Converter of published points to coordinates on a requested datum.

    Transformations are built on first use and cached, since finding the operation
    between two datums is far slower than applying it.
    """

    def __init__(self) -> None:
        self._transformations: dict[tuple[GeodeticCrs, GeodeticCrs], DatumTransformation] = {}

    def to_coordinate(self, point: RepresentativePoint, target: GeodeticCrs) -> GeoCoordinate:
        """
        Express a point on a datum.

        Parameters
        ----------
        point : RepresentativePoint
            Point on its published datum.
        target : GeodeticCrs
            Datum of the result.

        Returns
        -------
        GeoCoordinate
            Coordinate of the point on ``target``.

        Raises
        ------
        RuntimeError
            If no transformation of known accuracy joins the datums.
        """
        coordinate = GeoCoordinate.from_degrees(point.latitude, point.longitude)
        if point.crs is target:
            return coordinate
        key = (point.crs, target)
        if key not in self._transformations:
            self._transformations[key] = DatumTransformation(source=point.crs, target=target)
        return self._transformations[key].transform(coordinate)
