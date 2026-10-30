from enum import IntEnum

from address_codec_jp.address import LotSystem


class LotSystemColumn(IntEnum):
    """
    Compact integer stored for a ``LotSystem``, as in the registry's ``rsdt_addr_flg``.

    Every lot row repeats its numbering system, so an integer keeps the tables and their
    indexes far smaller than the enum's text value.

    Attributes
    ----------
    LAND_PARCEL
        Stored value of ``LotSystem.LAND_PARCEL``.
    RESIDENCE_INDICATION
        Stored value of ``LotSystem.RESIDENCE_INDICATION``.
    """

    LAND_PARCEL = 0
    RESIDENCE_INDICATION = 1

    @classmethod
    def encode(cls, lot_system: LotSystem) -> int:
        """
        Convert a numbering system to its stored value.

        Parameters
        ----------
        lot_system : LotSystem
            Numbering system to store.

        Returns
        -------
        int
            Column value.
        """
        match lot_system:
            case LotSystem.LAND_PARCEL:
                return cls.LAND_PARCEL.value
            case LotSystem.RESIDENCE_INDICATION:
                return cls.RESIDENCE_INDICATION.value

    @classmethod
    def decode(cls, value: object) -> LotSystem:
        """
        Convert a stored value back to its numbering system.

        Parameters
        ----------
        value : object
            Column value read from SQLite, as an integer or its text form.

        Returns
        -------
        LotSystem
            Numbering system the value stands for.

        Raises
        ------
        ValueError
            If the value is not a stored numbering system.
        """
        return cls(int(str(value))).lot_system

    @property
    def lot_system(self) -> LotSystem:
        """
        Numbering system of the stored value.

        Returns
        -------
        LotSystem
            Domain value.
        """
        match self:
            case LotSystemColumn.LAND_PARCEL:
                return LotSystem.LAND_PARCEL
            case LotSystemColumn.RESIDENCE_INDICATION:
                return LotSystem.RESIDENCE_INDICATION
