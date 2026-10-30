from collections.abc import Sequence
from dataclasses import replace
from typing import ClassVar, assert_never

from address_codec_jp.address import AddressCode, AddressLevel
from address_codec_jp.errors import AddressNotFoundError, AmbiguousAddressError
from address_codec_jp.results import AddressMatch, GroupMatch
from address_codec_jp.text.matching.area_matcher import AreaMatcher
from address_codec_jp.text.normalization import TextNormalizer


class GroupMatcher:
    """
    Matcher of addresses that all lie in one common area.

    Each address is first matched on its own. The common area is the narrowest
    prefecture, municipality, or town that encloses a candidate of every address,
    counting the matched code of an unambiguous address as its only candidate. When
    exactly one such area exists, the ambiguous addresses are matched again within it,
    so ``府中市`` is read as 東京都府中市 next to ``千代田区丸の内1-1``. The group fails
    as a whole when an address is not found, no common area exists, the narrowest common
    area is not unique, or an address stays ambiguous within it.

    Parameters
    ----------
    area_matcher : AreaMatcher
        Matcher of single addresses.
    normalizer : TextNormalizer
        Normalizer applied to the input addresses.
    """

    _AREA_LEVELS: ClassVar[frozenset[AddressLevel]] = frozenset(
        {AddressLevel.PREFECTURE, AddressLevel.MUNICIPALITY, AddressLevel.TOWN}
    )

    def __init__(self, area_matcher: AreaMatcher, normalizer: TextNormalizer) -> None:
        self._area_matcher: AreaMatcher = area_matcher
        self._normalizer: TextNormalizer = normalizer

    def match(self, addresses: Sequence[str]) -> GroupMatch:
        """
        Interpret addresses on the assumption that they lie in one common area.

        Parameters
        ----------
        addresses : Sequence[str]
            Addresses in any common notation. A leading postal code is used as by
            ``AreaMatcher.match``.

        Returns
        -------
        GroupMatch
            Common area and the match of each address within it.

        Raises
        ------
        TypeError
            If ``addresses`` is a single string instead of a sequence of addresses.
        ValueError
            If no address is given, an address is blank or only a postal code, or a lot
            number exceeds ``LotNumber.MAX_NUMBER``.
        AddressNotFoundError
            If an address does not match a registered area, or no area encloses a
            candidate of every address.
        AmbiguousAddressError
            If several narrowest common areas exist, or an address fits several areas or
            lot numbers equally well within the common area.
        DatasetNotImportedError
            If the repository contains no towns.
        """
        if isinstance(addresses, str):
            raise TypeError("Give a sequence of addresses, not a single string.")
        if not addresses:
            raise ValueError("At least one address is required.")
        normalized_addresses = [self._normalizer.normalize(address) for address in addresses]
        for index, (address, normalized_address) in enumerate(
            zip(addresses, normalized_addresses, strict=True)
        ):
            if not normalized_address:
                raise ValueError(f"Address {index}: {self._normalizer.describe_empty(address)}")
        postal_codes = [self._normalizer.extract_postal_code(address) for address in addresses]
        outcomes = [
            self._area_matcher.interpret(normalized_address, postal_code)
            for normalized_address, postal_code in zip(
                normalized_addresses, postal_codes, strict=True
            )
        ]
        candidate_groups: list[tuple[AddressCode, ...]] = []
        for outcome in outcomes:
            match outcome:
                case AddressMatch():
                    candidate_groups.append((outcome.code,))
                case AmbiguousAddressError():
                    candidate_groups.append(outcome.candidates)
                case AddressNotFoundError():
                    raise outcome
                case _:
                    assert_never(outcome)
        area = self._find_common_area(candidate_groups)
        return GroupMatch(
            area=area,
            matches=[
                self._restore_remainder(
                    address,
                    outcome
                    if isinstance(outcome, AddressMatch)
                    else self._area_matcher.match(normalized_address, postal_code, within=area),
                )
                for address, outcome, normalized_address, postal_code in zip(
                    addresses, outcomes, normalized_addresses, postal_codes, strict=True
                )
            ],
        )

    def _restore_remainder(self, address: str, address_match: AddressMatch) -> AddressMatch:
        return replace(
            address_match,
            remainder=self._normalizer.find_original_suffix(address, address_match.remainder),
        )

    def _find_common_area(self, candidate_groups: list[tuple[AddressCode, ...]]) -> AddressCode:
        enclosing_areas = [
            {
                area
                for candidate in candidates
                for area in candidate.lineage()
                if area.level in self._AREA_LEVELS
            }
            for candidates in candidate_groups
        ]
        common_areas = enclosing_areas[0].intersection(*enclosing_areas[1:])
        narrowest_areas = sorted(
            (
                area
                for area in common_areas
                if not any(other != area and area.contains(other) for other in common_areas)
            ),
            key=str,
        )
        match narrowest_areas:
            case []:
                raise AddressNotFoundError(
                    "No prefecture, municipality, or town encloses every address."
                )
            case [area]:
                return area
            case _:
                raise AmbiguousAddressError(
                    "The addresses fit in several areas equally well: "
                    + f"{', '.join(map(str, narrowest_areas))}.",
                    tuple(narrowest_areas),
                )
