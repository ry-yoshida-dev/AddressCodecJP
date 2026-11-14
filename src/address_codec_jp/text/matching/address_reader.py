from collections.abc import Sequence
from dataclasses import replace

from address_codec_jp.address import Address, AddressCode, LotNumber
from address_codec_jp.results import AddressMatch, GroupMatch
from address_codec_jp.text.matching.group_matcher import GroupMatcher
from address_codec_jp.text.matching.name_searcher import NameSearcher
from address_codec_jp.text.matching.reading.area_matcher import AreaMatcher
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
        self._lot_parser: LotNumberParser = LotNumberParser()
        self._matcher: AreaMatcher = AreaMatcher(towns, self._normalizer, self._lot_parser)
        self._group_matcher: GroupMatcher = GroupMatcher(self._matcher, self._normalizer)
        self._name_searcher: NameSearcher = NameSearcher(
            towns, self._normalizer, self._matcher.municipality_names
        )

    def match(
        self, address: str, within: AddressCode | None, *, is_partial_match_allowed: bool = False
    ) -> AddressMatch:
        """
        Interpret a free-form address.

        Parameters
        ----------
        address : str
            Address in any common notation.
        within : AddressCode | None
            Area the address must lie in, or ``None`` to search everywhere.
        is_partial_match_allowed : bool
            Whether an address whose town is not found matches its municipality or
            prefecture.

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
            normalized_address,
            self._normalizer.extract_postal_code(address),
            within=within,
            is_partial_match_allowed=is_partial_match_allowed,
        )
        return replace(
            address_match,
            remainder=self._normalizer.find_original_suffix(address, address_match.remainder),
        )

    def extend_lot(self, address_match: AddressMatch) -> AddressMatch | None:
        """
        Read a number at the start of the remainder as the third lot number.

        ``match`` leaves the ``4`` of ``2-3-4`` in the remainder, because it is usually
        a room number; a caller that can check the registry tries this reading too.

        Parameters
        ----------
        address_match : AddressMatch
            Match with two lot numbers.

        Returns
        -------
        AddressMatch | None
            Match with the number as the third lot number and the rest as remainder, or
            ``None`` when the match does not have two lot numbers or the remainder does
            not start with a number.
        """
        lot = address_match.address.lot
        if len(lot.numbers) != 2 or lot.system is None:
            return None
        extension = self._lot_parser.parse_hyphenated_number(
            self._normalizer.normalize(address_match.remainder)
        )
        if extension is None or extension[0] > LotNumber.MAX_NUMBER:
            return None
        number, rest = extension
        return replace(
            address_match,
            address=replace(
                address_match.address,
                lot=LotNumber(
                    block=lot.block, residence=lot.residence, branch=number, system=lot.system
                ),
            ),
            remainder=self._normalizer.find_original_suffix(address_match.remainder, rest),
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
