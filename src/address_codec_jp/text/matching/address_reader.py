from collections.abc import Sequence
from dataclasses import replace

from address_codec_jp.address import Address, AddressCode
from address_codec_jp.results import AddressMatch, GroupMatch
from address_codec_jp.text.matching.area_matcher import AreaMatcher
from address_codec_jp.text.matching.group_matcher import GroupMatcher
from address_codec_jp.text.matching.name_searcher import NameSearcher
from address_codec_jp.text.matching.town_source import TownSource
from address_codec_jp.text.normalization import LotNumberParser, TextNormalizer


class AddressReader:
    """
    Reader of free-form address text into registered areas.

    Text is normalized before it is matched, and the remainder of a match is returned
    as written in the input. The matching indexes are built on first use and shared by
    single matches, group matches, and name searches.

    Parameters
    ----------
    towns : TownSource
        Municipality, town, oaza, and koaza names to match against.
    """

    def __init__(self, towns: TownSource) -> None:
        self._normalizer: TextNormalizer = TextNormalizer()
        self._matcher: AreaMatcher = AreaMatcher(towns, self._normalizer, LotNumberParser())
        self._group_matcher: GroupMatcher = GroupMatcher(self._matcher, self._normalizer)
        self._name_searcher: NameSearcher = NameSearcher(
            towns, self._normalizer, self._matcher.municipality_names
        )

    def match(self, address: str, within: AddressCode | None) -> AddressMatch:
        """
        Interpret a free-form address.

        Parameters
        ----------
        address : str
            Address in any common notation.
        within : AddressCode | None
            Area the address must lie in, or ``None`` to search everywhere.

        Returns
        -------
        AddressMatch
            Matched address and the unparsed remainder as written.

        Raises
        ------
        ValueError
            If the address is blank or only a postal code.
        """
        normalized_address = self._normalizer.normalize(address)
        if not normalized_address:
            raise ValueError(self._normalizer.describe_empty(address))
        address_match = self._matcher.match(
            normalized_address, self._normalizer.extract_postal_code(address), within=within
        )
        return replace(
            address_match,
            remainder=self._normalizer.find_original_suffix(address, address_match.remainder),
        )

    def match_group(self, addresses: Sequence[str]) -> GroupMatch:
        """
        Interpret addresses that all lie in one common area.

        Parameters
        ----------
        addresses : Sequence[str]
            Addresses in any common notation.

        Returns
        -------
        GroupMatch
            Common area and the match of each address within it, in input order.
        """
        return self._group_matcher.match(addresses)

    def search_names(self, name: str, within: AddressCode | None) -> list[Address]:
        """
        List every registered area that bears a name.

        Parameters
        ----------
        name : str
            Name of an area, optionally after the prefecture or municipality.
        within : AddressCode | None
            Area the listed areas must lie in, or ``None`` to search everywhere.

        Returns
        -------
        list[Address]
            Areas ordered by code.

        Raises
        ------
        ValueError
            If the name is blank.
        """
        normalized_name = self._normalizer.normalize(name)
        if not normalized_name:
            raise ValueError("Name must not be blank.")
        return self._name_searcher.search(normalized_name, within=within)

    def parse_postal_code(self, postal_code: str) -> str:
        """
        Read a postal code written in any common notation.

        Parameters
        ----------
        postal_code : str
            Postal code such as ``100-0005``, ``〒1000005``, or with full-width digits.

        Returns
        -------
        str
            Seven-digit postal code.

        Raises
        ------
        ValueError
            If the text is not a postal code.
        """
        return self._normalizer.parse_postal_code(postal_code)
