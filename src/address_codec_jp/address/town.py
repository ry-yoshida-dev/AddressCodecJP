import re
from dataclasses import dataclass
from typing import ClassVar

from address_codec_jp.address.code import AddressCode
from address_codec_jp.address.lot_system import LotSystem
from address_codec_jp.address.municipality import Municipality


@dataclass(frozen=True, slots=True)
class Town:
    """
    Town (町字) record of the Address Base Registry.

    Parameters
    ----------
    municipality : Municipality
        Municipality that contains the town.
    machiaza_id : str
        Seven-digit town identifier unique within the municipality.
    oaza_name : str
        Oaza or town name (大字・町名).
    chome_name : str
        Chome name as registered, e.g. ``一丁目``, or an empty string.
    chome_number : int | None
        Numeric chome derived from ``chome_name``. ``None`` when there is no numeric chome.
    koaza_name : str
        Koaza name (小字名), or an empty string.
    oaza_kana : str
        Katakana reading of ``oaza_name``.
    chome_kana : str
        Katakana reading of ``chome_name``, such as ``１チョウメ``.
    koaza_kana : str
        Katakana reading of ``koaza_name``.
    lot_systems : frozenset[LotSystem]
        Numbering systems of the lot numbers, given by the residence indication flag
        (``rsdt_addr_flg``) of the registry. Both where residence indication covers only
        part of the town. Residence indication towns also keep land parcel numbers.
    postal_codes : tuple[str, ...]
        Seven-digit postal codes registered for the town, in ascending order. The
        registry gives them only for some towns.
    is_registered : bool
        ``False`` for an oaza-level town that this library added because the registry
        lists the oaza only by chome. Such a town cannot carry lot numbers, because lot
        numbers of that oaza belong to one of its chome.
    is_street_direction : bool
        Whether the koaza is a street direction of Kyoto (通り名) such as
        ``烏丸通塩小路下る``, given by ``koaza_aka_code`` ``2`` of the registry. Such a
        koaza locates the town along its streets, while the lot numbers belong to the
        oaza, and it is written before the oaza name.

    Readings are empty strings when the name is empty or the registry has no reading.

    Raises
    ------
    ValueError
        If ``machiaza_id`` or a postal code is malformed, or no numbering system is given.
    """

    municipality: Municipality
    machiaza_id: str
    oaza_name: str
    chome_name: str
    chome_number: int | None
    koaza_name: str
    oaza_kana: str
    chome_kana: str
    koaza_kana: str
    lot_systems: frozenset[LotSystem]
    postal_codes: tuple[str, ...]
    is_registered: bool
    is_street_direction: bool

    _POSTAL_CODE: ClassVar[re.Pattern[str]] = re.compile(r"[0-9]{7}")

    def __post_init__(self) -> None:
        _ = AddressCode(lg_code=self.lg_code, machiaza_id=self.machiaza_id)
        if not self.lot_systems:
            raise ValueError("A town requires at least one numbering system.")
        for postal_code in self.postal_codes:
            if not self._POSTAL_CODE.fullmatch(postal_code):
                raise ValueError(f"Postal codes must be seven digits, got {postal_code!r}.")

    @property
    def lg_code(self) -> str:
        """
        Local government code of the municipality.

        Returns
        -------
        str
            Six-digit local government code.
        """
        return self.municipality.lg_code
