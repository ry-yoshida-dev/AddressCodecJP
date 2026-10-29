from dataclasses import dataclass, field

from address_codec_jp.domain.address_code import AddressCode
from address_codec_jp.domain.lot_number import LotNumber
from address_codec_jp.domain.municipality import Municipality
from address_codec_jp.domain.prefecture import Prefecture
from address_codec_jp.domain.town import Town


@dataclass(frozen=True, slots=True)
class Address:
    """
    Registered areas and lot numbers that an address code stands for.

    Parameters
    ----------
    prefecture : Prefecture
        Prefecture of the address.
    municipality : Municipality | None
        Municipality. ``None`` when the address ends at the prefecture.
    town : Town | None
        Town. ``None`` when the address ends at the prefecture or municipality.
    lot : LotNumber
        Block and residence numbers. Empty unless a town is given.

    Raises
    ------
    ValueError
        If a town is given without a municipality, lot numbers without a town, lot
        numbers on an oaza that takes them only under a chome, or the areas do not
        contain each other.
    """

    prefecture: Prefecture
    municipality: Municipality | None = None
    town: Town | None = None
    lot: LotNumber = field(default_factory=LotNumber)

    def __post_init__(self) -> None:
        if self.municipality is not None and self.municipality.prefecture != self.prefecture:
            raise ValueError(
                f"Municipality {self.municipality.lg_code} is not in prefecture "
                + f"{self.prefecture.code}."
            )
        if self.town is not None:
            if self.municipality is None:
                raise ValueError("A town requires a municipality.")
            if self.town.municipality != self.municipality:
                raise ValueError(
                    f"Town {self.town.machiaza_id} is not in municipality "
                    + f"{self.municipality.lg_code}."
                )
            if not self.town.is_registered and self.lot.numbers:
                raise ValueError(
                    f"{self.town.oaza_name} takes lot numbers only under a chome, "
                    + f"got {self.lot.numbers}."
                )
        elif self.lot.numbers:
            raise ValueError("Lot numbers require a town.")

    @property
    def code(self) -> AddressCode:
        """
        Address code of the address.

        Returns
        -------
        AddressCode
            Code at the most specific level of the address.
        """
        if self.town is not None:
            return AddressCode(
                lg_code=self.town.lg_code, machiaza_id=self.town.machiaza_id, lot=self.lot
            )
        if self.municipality is not None:
            return AddressCode(lg_code=self.municipality.lg_code)
        return AddressCode.for_prefecture(self.prefecture.code)
