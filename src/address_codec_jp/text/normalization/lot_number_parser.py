import re
from typing import ClassVar

from address_codec_jp.address import LotNumber, LotSystem
from address_codec_jp.text.normalization.lot_parse_result import LotParseResult


class LotNumberParser:
    """
    Parser for lot numbers in normalized text.

    Accepted notations include ``2番3号``, ``2番地3``, ``2番地の3``, ``2-3`` and ``2の3``.
    A third number is read when ``の`` introduces it (``124番地1の1``, ``2-3の4``) or
    ``号`` closes it (``2番3-4号``). After a dash without ``号`` it is left in the
    remainder, because ``2-3-405`` usually ends with a room number.
    A leading dash, or ``の`` or ``字`` before a number, separates the lot numbers from
    the town name (``八方谷1の16``, ``林町字148-1``).
    A number followed by a floor, building, or room marker such as ``3階``, ``2F``,
    ``2号館``, or ``101号室`` belongs to the building and is not read as a lot number.

    ``番地`` marks land parcel numbers and ``番`` with ``号`` residence indication; the
    marked system is reported as ``LotParseResult.notation``.
    """

    _BUILDING_MARKER: ClassVar[str] = r"(?:[号番]?[館棟室]|階|[Ff](?![A-Za-z]))"
    _NUMBER_END: ClassVar[str] = rf"(?![0-9丁]|{_BUILDING_MARKER})"
    _LOT: ClassVar[re.Pattern[str]] = re.compile(
        rf"(?P<block>[1-9][0-9]*){_NUMBER_END}(?P<block_marker>番地|番)?"
        + rf"(?:[-のノ之]?(?P<residence>[1-9][0-9]*){_NUMBER_END}"
        + r"(?P<residence_marker>号|番地|番)?"
        + r"(?:(?:(?<![号番地])-(?P<closed_branch>[1-9][0-9]*)(?=号(?![館棟室]))"
        + rf"|[のノ之](?P<branch>[1-9][0-9]*){_NUMBER_END})(?P<branch_marker>号|番地|番)?)?)?"
    )
    _LEADING_SEPARATOR: ClassVar[re.Pattern[str]] = re.compile("^(?:-+|[のノ之字](?=[1-9]))")
    _BUILDING_NUMBER: ClassVar[re.Pattern[str]] = re.compile(rf"[0-9]+{_BUILDING_MARKER}")
    _HYPHENATED_NUMBER: ClassVar[re.Pattern[str]] = re.compile(
        rf"^-?(?P<number>[1-9][0-9]*){_NUMBER_END}(?:号(?![館棟室]))?"
    )

    def parse(self, normalized_text: str) -> LotParseResult:
        """
        Parse lot numbers at the start of the text.

        Parameters
        ----------
        normalized_text : str
            Text after the town name, already normalized by ``TextNormalizer``.

        Returns
        -------
        LotParseResult
            Parsed lot numbers, the numbering system their notation marks, and the
            remaining text.
        """
        normalized_text = self._LEADING_SEPARATOR.sub("", normalized_text)
        matched = self._LOT.match(normalized_text)
        if matched is None:
            return LotParseResult(lot=LotNumber(), notation=None, remainder=normalized_text)
        numbers = [
            int(number)
            for number in (
                matched.group("block"),
                matched.group("residence"),
                matched.group("branch") or matched.group("closed_branch"),
            )
            if number is not None
        ]
        notation = self._notation(matched)
        return LotParseResult(
            lot=LotNumber.of(numbers, notation or LotSystem.RESIDENCE_INDICATION),
            notation=notation,
            remainder=normalized_text[matched.end() :].lstrip("-"),
        )

    def parse_hyphenated_number(self, normalized_text: str) -> tuple[int, str] | None:
        """
        Read a number at the start of the remainder as a further lot number.

        It is the third number of ``2-3-4`` that ``parse`` leaves in the remainder, as
        it may be a room number.

        Parameters
        ----------
        normalized_text : str
            Remainder after the lot numbers, normalized, such as ``4`` or ``-405``.

        Returns
        -------
        tuple[int, str] | None
            The number and the text after it, or ``None`` when the text does not start
            with a number, or the number is a floor, building, or room number.
        """
        matched = self._HYPHENATED_NUMBER.match(normalized_text)
        if matched is None:
            return None
        return int(matched.group("number")), normalized_text[matched.end() :].lstrip("-")

    def is_building_number(self, normalized_text: str) -> bool:
        """
        Tell whether the text starts with a floor, building, or room number.

        Parameters
        ----------
        normalized_text : str
            Text left after the town name and lot numbers.

        Returns
        -------
        bool
            ``True`` for text such as ``3階``, ``2F``, or ``2号館ビル``.
        """
        return self._BUILDING_NUMBER.match(normalized_text) is not None

    def _notation(self, matched: re.Match[str]) -> LotSystem | None:
        markers = {
            matched.group("block_marker"),
            matched.group("residence_marker"),
            matched.group("branch_marker"),
        }
        if "番地" in markers:
            return LotSystem.LAND_PARCEL
        if "号" in markers or matched.group("closed_branch") is not None:
            return LotSystem.RESIDENCE_INDICATION
        return None
