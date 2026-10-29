from collections.abc import Iterator
from typing import ClassVar

from geo_coordinate import GeodeticCrs

from address_codec_jp.domain.address_code import AddressCode
from address_codec_jp.domain.address_level import AddressLevel
from address_codec_jp.domain.address_location import AddressLocation
from address_codec_jp.domain.lot_number import LotNumber
from address_codec_jp.domain.lot_system import LotSystem
from address_codec_jp.domain.position_level import PositionLevel
from address_codec_jp.domain.representative_point import RepresentativePoint
from address_codec_jp.positioning.datum_converter import DatumConverter
from address_codec_jp.storage.position_repository import PositionRepository


class AddressLocator:
    """
    Finder of the representative point of an address code.

    The code itself is tried first, then its enclosing areas from the most specific:
    block, town, oaza (for a chome or koaza), municipality, and prefecture.

    Parameters
    ----------
    repository : PositionRepository
        Imported representative points.
    """

    _OAZA_CHOME_PART: ClassVar[str] = "000"
    _UNKNOWN_TOWN_LOT_SYSTEMS: ClassVar[tuple[LotSystem, ...]] = (
        LotSystem.RESIDENCE_INDICATION,
        LotSystem.LAND_PARCEL,
    )

    def __init__(self, repository: PositionRepository) -> None:
        self._repository: PositionRepository = repository
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
        RuntimeError
            If no position has been imported, or the published datum cannot be
            transformed to ``crs``.
        LookupError
            If neither the code nor any enclosing area has a point.
        """
        if not self._repository.is_position_imported:
            raise RuntimeError("No positions have been imported. Import position datasets.")
        for candidate in self._candidates(code):
            point = self._find_point(candidate)
            if point is not None:
                return AddressLocation(
                    code=code,
                    located_code=candidate,
                    coordinate=self._converter.to_coordinate(point, crs),
                    crs=crs,
                )
        raise LookupError(f"No position is imported for {code} or its enclosing areas.")

    def _candidates(self, code: AddressCode) -> Iterator[AddressCode]:
        if code.machiaza_id is not None:
            if code.lot.residence is not None:
                yield code
            if code.lot.block is not None:
                yield AddressCode(
                    lg_code=code.lg_code,
                    machiaza_id=code.machiaza_id,
                    lot=LotNumber(block=code.lot.block),
                )
            yield AddressCode(lg_code=code.lg_code, machiaza_id=code.machiaza_id)
            oaza_id = code.machiaza_id[:4] + self._OAZA_CHOME_PART
            if oaza_id != code.machiaza_id:
                yield AddressCode(lg_code=code.lg_code, machiaza_id=oaza_id)
        if code.level is not AddressLevel.PREFECTURE:
            yield AddressCode(lg_code=code.lg_code)
        yield AddressCode.for_prefecture(code.prefecture_code)

    def _find_point(self, code: AddressCode) -> RepresentativePoint | None:
        match PositionLevel.of(code):
            case PositionLevel.PREFECTURE | PositionLevel.MUNICIPALITY:
                return self._repository.find_area(code.lg_code)
            case PositionLevel.TOWN | PositionLevel.BLOCK | PositionLevel.RESIDENCE:
                if code.machiaza_id is None:
                    raise RuntimeError("A town-level code must have a machiaza_id.")
                town = self._repository.find_town(code.lg_code, code.machiaza_id)
                if not code.lot.numbers:
                    return None if town is None else town.point
                lot_systems = self._UNKNOWN_TOWN_LOT_SYSTEMS if town is None else (town.lot_system,)
                return self._repository.find_lot(
                    code.lg_code, code.machiaza_id, lot_systems, code.lot
                )
