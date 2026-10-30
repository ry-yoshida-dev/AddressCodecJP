from dataclasses import dataclass

from address_codec_jp.address import Address, AddressCode
from address_codec_jp.results.match_tier import MatchTier


@dataclass(frozen=True, slots=True)
class AddressMatch:
    """
    Result of interpreting a free-form address.

    Parameters
    ----------
    address : Address
        Matched prefecture, municipality, town, and lot numbers.
    remainder : str
        Trailing text that is not part of the code, such as a building name or room number,
        as written in the input.
    normalized_address : str
        Input after text normalization.
    postal_code : str | None
        Seven-digit postal code written at the start of the input, or ``None``.
    town_name_tier : MatchTier | None
        Loosest comparison needed to match the oaza and koaza names, or ``None`` when
        the address ends at the prefecture or municipality.
    """

    address: Address
    remainder: str
    normalized_address: str
    postal_code: str | None
    town_name_tier: MatchTier | None

    @property
    def code(self) -> AddressCode:
        """
        Address code of the match.

        Returns
        -------
        AddressCode
            Code at the most specific level that was matched.
        """
        return self.address.code
