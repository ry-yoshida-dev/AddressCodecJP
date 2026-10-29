from collections.abc import Sequence
from typing import Protocol

from address_codec_jp.domain.address_point import AddressPoint
from address_codec_jp.domain.coordinate_bounds import CoordinateBounds
from address_codec_jp.domain.lot_number import LotNumber
from address_codec_jp.domain.lot_system import LotSystem
from address_codec_jp.domain.representative_point import RepresentativePoint
from address_codec_jp.domain.town_position import TownPosition


class PositionSource(Protocol):
    """Read access to the representative points that locating needs."""

    @property
    def is_position_imported(self) -> bool:
        """
        Tell whether any point of a prefecture, municipality, or town is available.

        Returns
        -------
        bool
            ``True`` when points can be looked up.
        """
        ...

    def find_area(self, lg_code: str) -> RepresentativePoint | None:
        """
        Fetch the point of a prefecture or municipality.

        Parameters
        ----------
        lg_code : str
            Six-digit local government code.

        Returns
        -------
        RepresentativePoint | None
            Point of the area, or ``None`` when none is available.
        """
        ...

    def find_town(self, lg_code: str, machiaza_id: str) -> TownPosition | None:
        """
        Fetch the point and lot numbering of a town.

        Parameters
        ----------
        lg_code : str
            Six-digit local government code.
        machiaza_id : str
            Seven-digit town identifier.

        Returns
        -------
        TownPosition | None
            Position of the town, or ``None`` when none is available.
        """
        ...

    def find_lot(
        self, lg_code: str, machiaza_id: str, lot_systems: Sequence[LotSystem], lot: LotNumber
    ) -> RepresentativePoint | None:
        """
        Fetch the point of a block, residence, or parcel by its numbers.

        Parameters
        ----------
        lg_code : str
            Six-digit local government code.
        machiaza_id : str
            Seven-digit town identifier.
        lot_systems : Sequence[LotSystem]
            Numbering systems to search, in order of preference.
        lot : LotNumber
            Block and residence numbers with a block.

        Returns
        -------
        RepresentativePoint | None
            Point of the first match, or ``None`` when none is available.
        """
        ...

    def list_lot_points(self, bounds: CoordinateBounds) -> list[AddressPoint]:
        """
        List the points of blocks, residences, and parcels within bounds.

        Parameters
        ----------
        bounds : CoordinateBounds
            Search area on the published datums.

        Returns
        -------
        list[AddressPoint]
            Codes with lot numbers and their points.
        """
        ...

    def list_town_points(self, bounds: CoordinateBounds) -> list[AddressPoint]:
        """
        List the points of towns within bounds.

        Parameters
        ----------
        bounds : CoordinateBounds
            Search area on the published datums.

        Returns
        -------
        list[AddressPoint]
            Town codes and their points.
        """
        ...
