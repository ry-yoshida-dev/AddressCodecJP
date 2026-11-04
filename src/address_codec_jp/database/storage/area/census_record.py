from dataclasses import dataclass

from address_codec_jp.address import AddressCode
from address_codec_jp.geometry import AreaShape


@dataclass(frozen=True, slots=True)
class CensusAreaRecord:
    """
    Stored small area of the census boundary data and the towns it is matched to.

    Every area of a municipality is stored, matched or not, so that the shape of the
    municipality never depends on how its names were matched.

    Parameters
    ----------
    key_code : str
        Census code of the area (KEY_CODE).
    lg_code : str
        Six-digit local government code of the municipality the area lies in.
    name : str
        Census name of the area, empty when the census leaves it unnamed.
    shape : AreaShape
        Shape on JGD2011.
    is_land : bool
        Whether the area is a town rather than a water area.
    towns : frozenset[AddressCode]
        Towns the area is matched to; empty for a water area or an area no single town
        fits.

    Raises
    ------
    ValueError
        If a town lies outside ``lg_code`` or is not a town code.
    """

    key_code: str
    lg_code: str
    name: str
    shape: AreaShape
    is_land: bool
    towns: frozenset[AddressCode]

    def __post_init__(self) -> None:
        for town in self.towns:
            if town.lg_code != self.lg_code or town.machiaza_id is None or town.lot.numbers:
                raise ValueError(f"{town} is not a town of {self.lg_code}.")
