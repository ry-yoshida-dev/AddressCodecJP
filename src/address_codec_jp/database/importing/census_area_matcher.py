from collections import Counter, defaultdict
from typing import ClassVar

from address_codec_jp.address import AddressCode
from address_codec_jp.datasets.boundaries import CensusArea
from address_codec_jp.text.matching import AreaMatcher, TownSource
from address_codec_jp.text.normalization import TextNormalizer


class CensusAreaMatcher:
    """
    Matcher from the areas of the census boundary data to registered towns.

    An area is first matched by its address like any written address. A census area
    whose name continues past a registered oaza, such as a group of koaza, becomes part
    of that oaza. The census also names towns differently from the registry: it leaves
    out the leading part that several oaza of the municipality share, often the name of a
    merged town (``三大寺`` for ``水口町三大寺``, ``三崎町`` for ``神田三崎町``), and sometimes
    a trailing ``町`` (``大塚`` for ``大塚町``). An area that matches no town is therefore
    read again with each shared leading part that the registry continues with its name,
    and with ``町`` appended, and taken when exactly one town then matches it whole. Of
    shared parts that both fit, the shorter is taken: ``泉`` is read as ``水口町泉``, not as
    ``水口町北泉`` after ``水口町北``, which ``北泉``, ``北脇`` and ``北内貴`` share.

    Parameters
    ----------
    towns : TownSource
        Registered municipalities and towns.
    normalizer : TextNormalizer
        Normalizer shared with ``matcher``.
    matcher : AreaMatcher
        Matcher of written addresses over ``towns``.
    """

    _MINIMUM_KOAZA_LENGTH: ClassVar[int] = 2
    _MINIMUM_SHARED_PART_LENGTH: ClassVar[int] = 2
    _MINIMUM_SHARING_OAZA_COUNT: ClassVar[int] = 3
    _SEPARATORS: ClassVar[str] = ",、，・"
    _TOWN_SUFFIX: ClassVar[str] = "町"

    def __init__(self, towns: TownSource, normalizer: TextNormalizer, matcher: AreaMatcher) -> None:
        self._towns: TownSource = towns
        self._normalizer: TextNormalizer = normalizer
        self._matcher: AreaMatcher = matcher
        self._shared_parts: dict[str, dict[str, set[str]]] = {}

    def match(self, area: CensusArea, lg_code: str) -> AddressCode | None:
        """
        Find the town an area belongs to.

        Parameters
        ----------
        area : CensusArea
            Area read from the boundary data.
        lg_code : str
            Six-digit local government code of the municipality the boundary data covers.
            The registry's names of its towns are used when the area matches no town as
            written; a prefecture code leaves that step out.

        Returns
        -------
        AddressCode | None
            Code of the town, or ``None`` when no town or several fit.
        """
        if not area.address.endswith(area.town_name):
            raise ValueError(f"Address {area.address!r} does not end with {area.town_name!r}.")
        code = self._match_as_written(area.address)
        if code is not None:
            return code
        municipality_text = area.address.removesuffix(area.town_name)
        codes_by_part = {
            part: candidate
            for part in self._list_shared_parts(area.town_name, lg_code)
            if (candidate := self._match_whole_town(municipality_text + part + area.town_name))
            is not None
        }
        codes = {
            candidate
            for part, candidate in codes_by_part.items()
            if not any(part != other and part.startswith(other) for other in codes_by_part)
        }
        if self._can_omit_town_suffix(area.town_name):
            suffixed = self._match_whole_town(
                municipality_text + area.town_name + self._TOWN_SUFFIX
            )
            if suffixed is not None:
                codes.add(suffixed)
        return codes.pop() if len(codes) == 1 else None

    def _match_as_written(self, address: str) -> AddressCode | None:
        matched = self._matcher.find(self._normalizer.normalize(address), None)
        if matched is None:
            return None
        code = matched.code
        remainder = matched.remainder
        if code.machiaza_id is None or code.lot.numbers:
            return None
        if not remainder:
            return code
        is_koaza_of_oaza = (
            code.machiaza_id.endswith("000")
            and len(remainder) >= self._MINIMUM_KOAZA_LENGTH
            and remainder[0] not in self._SEPARATORS
        )
        return code if is_koaza_of_oaza else None

    def _match_whole_town(self, address: str) -> AddressCode | None:
        matched = self._matcher.find(self._normalizer.normalize(address), None)
        if matched is None or matched.remainder:
            return None
        code = matched.code
        return None if code.machiaza_id is None or code.lot.numbers else code

    def _list_shared_parts(self, town_name: str, lg_code: str) -> set[str]:
        folded = self._normalizer.fold(self._normalizer.normalize(town_name))
        parts_by_rest = self._map_shared_parts(lg_code)
        return {
            part
            for length in range(1, len(folded) + 1)
            for part in parts_by_rest.get(folded[:length], ())
        }

    def _can_omit_town_suffix(self, town_name: str) -> bool:
        normalized = self._normalizer.normalize(town_name)
        is_plain_name = not any(character.isdigit() for character in normalized)
        return is_plain_name and not normalized.endswith(self._TOWN_SUFFIX)

    def _map_shared_parts(self, lg_code: str) -> dict[str, set[str]]:
        if lg_code in self._shared_parts:
            return self._shared_parts[lg_code]
        oaza_names = {
            self._normalizer.normalize(town.oaza_name)
            for town in self._towns.list_towns(lg_code)
            if town.oaza_name
        }
        sharing_counts = Counter(
            name[:length]
            for name in oaza_names
            for length in range(self._MINIMUM_SHARED_PART_LENGTH, len(name))
        )
        parts_by_rest: dict[str, set[str]] = defaultdict(set)
        for name in oaza_names:
            for length in range(self._MINIMUM_SHARED_PART_LENGTH, len(name)):
                part = name[:length]
                if sharing_counts[part] >= self._MINIMUM_SHARING_OAZA_COUNT:
                    parts_by_rest[self._normalizer.fold(name[length:])].add(part)
        self._shared_parts[lg_code] = dict(parts_by_rest)
        return self._shared_parts[lg_code]
