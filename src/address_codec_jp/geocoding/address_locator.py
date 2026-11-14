from geo_coordinate import GeodeticCrs

from address_codec_jp.address import AddressCode
from address_codec_jp.errors import DatasetNotImportedError, PositionNotFoundError
from address_codec_jp.geocoding.datum_converter import DatumConverter
from address_codec_jp.geocoding.position_source import PositionSource
from address_codec_jp.geometry import RepresentativePoint
from address_codec_jp.results import AddressLocation


class AddressLocator:
    """
    Finder of the representative point of an address code.

    The code itself is tried first, then its enclosing areas given by
    ``AddressCode.lineage``: residence and block (for residence indication), town, oaza
    (for a chome or koaza), municipality, and prefecture. Lot numbers are looked up in
    their own numbering system only.

    Parameters
    ----------
    repository : PositionSource
        Imported representative points, such as ``PositionRepository``.
    """

    def __init__(self, repository: PositionSource) -> None:
        self._repository: PositionSource = repository
        self._converter: DatumConverter = DatumConverter()

    def locate(self, code: AddressCode, crs: GeodeticCrs) -> AddressLocation:
        """
        Find the representative point of an address code.

        Parameters
        ----------
        code : AddressCode
            Address code to locate.
        crs : GeodeticCrs
            Datum of the returned coordinate.

        Returns
        -------
        AddressLocation
            Point of the code or of its nearest enclosing area that has one.

        Raises
        ------
        DatasetNotImportedError
            If no position has been imported.
        PositionNotFoundError
            If neither the code nor any enclosing area has a point.
        RuntimeError
            If the published datum cannot be transformed to ``crs``.
        """
        if not self._repository.is_position_imported:
            raise DatasetNotImportedError(
                "No positions have been imported. Import position datasets."
            )
        for candidate in code.lineage():
            point = self._find_point(candidate)
            if point is not None:
                return AddressLocation(
                    code=code,
                    located_code=candidate,
                    coordinate=self._converter.to_coordinate(point, crs),
                    crs=crs,
                )
        raise PositionNotFoundError(f"No position is imported for {code} or its enclosing areas.")

    def _find_point(self, code: AddressCode) -> RepresentativePoint | None:
        if code.machiaza_id is None:
            return self._repository.find_area(code.lg_code)
        if code.lot.numbers:
            return self._repository.find_lot(code.lg_code, code.machiaza_id, code.lot)
        town = self._repository.find_town(code.lg_code, code.machiaza_id)
        return None if town is None else town.point
