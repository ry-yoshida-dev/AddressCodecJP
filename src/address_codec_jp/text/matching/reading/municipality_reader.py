from collections.abc import Container
from dataclasses import replace

from address_codec_jp.address import AddressCode, Municipality, Prefecture
from address_codec_jp.text.matching.index.municipality_name_index import MunicipalityNameIndex
from address_codec_jp.text.matching.reading.municipality_match import MunicipalityMatch
from address_codec_jp.text.matching.town_source import TownSource
from address_codec_jp.text.normalization import TextNormalizer


class MunicipalityReader:
    """
    Reader of the prefecture and municipality names at the start of an address.

    Municipality names are matched by every prefix, longest first, and with the forms
    that ``MunicipalityNameIndex`` registers: without the prefecture or county, with the
    prefecture written without ``都``/``府``/``県``, and without the ward of a designated
    city. A ward written without its city is matched after every full name. The matched
    municipalities can be narrowed to an area or by a postal code.

    Parameters
    ----------
    repository : TownSource
        Source of the municipalities and of the municipalities of a postal code.
    normalizer : TextNormalizer
        Normalizer applied to the names.
    """

    def __init__(self, repository: TownSource, normalizer: TextNormalizer) -> None:
        self._repository: TownSource = repository
        self._normalizer: TextNormalizer = normalizer
        self._names: MunicipalityNameIndex = MunicipalityNameIndex(repository, normalizer)

    @property
    def names(self) -> MunicipalityNameIndex:
        """Prefecture and municipality names of the repository, built on first use."""
        return self._names

    def match_prefecture(self, text: str) -> tuple[Prefecture | None, str]:
        """
        Read the prefecture name at the start of a normalized address.

        Parameters
        ----------
        text : str
            Address normalized by ``TextNormalizer.normalize``.

        Returns
        -------
        tuple[Prefecture | None, str]
            Longest matching prefecture and the text after it, or ``None`` and the whole
            text when no prefecture name starts the text.
        """
        index = self._names.prefectures
        keys = self.matching_prefixes(self._normalizer.fold(text), index)
        if not keys:
            return None, text
        return index[keys[0]], text[len(keys[0]) :]

    def match_all(self, text: str) -> list[MunicipalityMatch]:
        """
        Read every municipality name that starts a normalized address.

        Parameters
        ----------
        text : str
            Address normalized by ``TextNormalizer.normalize``.

        Returns
        -------
        list[MunicipalityMatch]
            Matches of full names, longest first, followed by matches of ward names
            written without their city.
        """
        index = self._names.municipalities
        ward_index = self._names.wards
        folded = self._normalizer.fold(text)
        full_name_matches = [
            self._to_match(
                text, key, index[key], is_name_abbreviated=key in self._names.abbreviated_keys
            )
            for key in self.matching_prefixes(folded, index)
        ]
        ward_matches = [
            self._to_match(text, key, ward_index[key], is_name_abbreviated=False)
            for key in self.matching_prefixes(folded, ward_index)
        ]
        return full_name_matches + ward_matches

    def narrow(
        self,
        municipality_match: MunicipalityMatch,
        within: AddressCode | None,
        postal_code: str | None,
    ) -> MunicipalityMatch:
        """
        Keep the municipalities of a match that lie in an area and have a postal code.

        Parameters
        ----------
        municipality_match : MunicipalityMatch
            Match to narrow.
        within : AddressCode | None
            Area the municipalities must overlap, or ``None`` to keep every one.
        postal_code : str | None
            Postal code written with the address, or ``None``.

        Returns
        -------
        MunicipalityMatch
            Match with the municipalities of the area. The postal code narrows only a
            match that needs a town name to decide, and only when it keeps any.
        """
        if within is not None:
            municipality_match = self._keep(
                municipality_match,
                [
                    municipality
                    for municipality in municipality_match.municipalities
                    if self.overlaps(municipality, within)
                ],
            )
        return self.narrow_by_postal_code(municipality_match, postal_code)

    def narrow_by_postal_code(
        self, municipality_match: MunicipalityMatch, postal_code: str | None
    ) -> MunicipalityMatch:
        """
        Keep the municipalities of a match that have a postal code.

        Parameters
        ----------
        municipality_match : MunicipalityMatch
            Match to narrow.
        postal_code : str | None
            Postal code written with the address, or ``None``.

        Returns
        -------
        MunicipalityMatch
            Match with the municipalities of the postal code, or the match unchanged when
            no postal code is given, no town name is needed to decide, or no municipality
            has the postal code.
        """
        if postal_code is None or not municipality_match.is_town_required:
            return municipality_match
        lg_codes = self._repository.list_municipality_codes(postal_code)
        selected = [
            municipality
            for municipality in municipality_match.municipalities
            if municipality.lg_code in lg_codes
        ]
        if not selected:
            return municipality_match
        return self._keep(municipality_match, selected)

    @staticmethod
    def overlaps(municipality: Municipality, within: AddressCode | None) -> bool:
        """
        Tell whether a municipality overlaps an area.

        Parameters
        ----------
        municipality : Municipality
            Municipality to check.
        within : AddressCode | None
            Area, or ``None`` for everywhere.

        Returns
        -------
        bool
            ``True`` when one contains the other.
        """
        if within is None:
            return True
        code = AddressCode(lg_code=municipality.lg_code)
        return within.contains(code) or code.contains(within)

    @staticmethod
    def matching_prefixes(text: str, keys: Container[str]) -> list[str]:
        """
        List the prefixes of a text that are keys, longest first.

        Parameters
        ----------
        text : str
            Text whose prefixes are looked up.
        keys : Container[str]
            Keys to look the prefixes up in.

        Returns
        -------
        list[str]
            Matching prefixes, longest first.
        """
        return [text[:length] for length in range(len(text), 0, -1) if text[:length] in keys]

    def _to_match(
        self,
        text: str,
        key: str,
        municipalities: frozenset[Municipality],
        *,
        is_name_abbreviated: bool,
    ) -> MunicipalityMatch:
        return MunicipalityMatch(
            name=text[: len(key)],
            municipalities=sorted(municipalities, key=lambda municipality: municipality.lg_code),
            remainder=text[len(key) :],
            is_name_abbreviated=is_name_abbreviated,
        )

    def _keep(
        self, municipality_match: MunicipalityMatch, selected: list[Municipality]
    ) -> MunicipalityMatch:
        return replace(
            municipality_match,
            municipalities=selected,
            is_name_abbreviated=municipality_match.is_name_abbreviated
            and (len(selected) > 1 or any(municipality.ward_name for municipality in selected)),
        )
