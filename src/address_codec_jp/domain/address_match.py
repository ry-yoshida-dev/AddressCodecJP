from dataclasses import dataclass

from address_codec_jp.domain.address_code import AddressCode
from address_codec_jp.domain.lot_number import LotNumber
from address_codec_jp.domain.municipality import Municipality
from address_codec_jp.domain.prefecture import Prefecture
from address_codec_jp.domain.town import Town


@dataclass(frozen=True, slots=True)
class AddressMatch:
    """
    Result of interpreting a free-form address.

    Parameters
    ----------
    normalized_address : str
        Input after text normalization.
    prefecture : Prefecture
        Matched prefecture.
    municipality : Municipality | None
        Matched municipality. ``None`` when the address ends at the prefecture.
    town : Town | None
        Matched town. ``None`` when the address ends at the prefecture or municipality.
    lot : LotNumber
        Parsed block and residence numbers.
    remainder : str
        Trailing text that is not part of the code, such as a building name or room number.

    Raises
    ------
    ValueError
        If a town is given without a municipality, or lot numbers without a town.
    """

    normalized_address: str
    prefecture: Prefecture
    municipality: Municipality | None
    town: Town | None
    lot: LotNumber
    remainder: str

    def __post_init__(self) -> None:
        if self.town is not None and self.municipality is None:
            raise ValueError("A town match requires a municipality.")
        if self.town is None and self.lot.numbers:
            raise ValueError("Lot numbers require a town.")

    @property
    def code(self) -> AddressCode:
        """
        Address code of the match.

        Returns
        -------
        AddressCode
            Code at the most specific level that was matched.
        """
        if self.town is not None:
            return AddressCode(
                lg_code=self.town.lg_code, machiaza_id=self.town.machiaza_id, lot=self.lot
            )
        if self.municipality is not None:
            return AddressCode(lg_code=self.municipality.lg_code)
        return AddressCode.for_prefecture(self.prefecture.code)
