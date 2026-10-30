import re
from typing import ClassVar

from address_codec_jp.address import LotNumber
from address_codec_jp.text.normalization.lot_parse_result import LotParseResult


class LotNumberParser:
    """
    Parser for block and residence numbers in normalized text.

    Accepted notations include ``2番3号``, ``2番地3``, ``2番地の3``, ``2-3`` and ``2の3``.
    A number followed by a floor, building, or room marker such as ``3階``, ``2F``,
    ``2号館``, or ``101号室`` belongs to the building and is not read as a lot number.
    """

    _BUILDING_MARKER: ClassVar[str] = r"(?:[号番]?[館棟室]|階|[Ff](?![A-Za-z]))"
    _LOT: ClassVar[re.Pattern[str]] = re.compile(
        rf"(?P<block>[1-9][0-9]*)(?![0-9丁]|{_BUILDING_MARKER})(?:番地|番)?"
        + rf"(?:[-のノ之]?(?P<residence>[1-9][0-9]*)(?![0-9丁]|{_BUILDING_MARKER})(?:号|番地|番)?)?"
    )
    _BUILDING_NUMBER: ClassVar[re.Pattern[str]] = re.compile(rf"[0-9]+{_BUILDING_MARKER}")

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
            Parsed lot numbers and the remaining text.
        """
        normalized_text = normalized_text.lstrip("-")
        matched = self._LOT.match(normalized_text)
        if matched is None:
            return LotParseResult(lot=LotNumber(), remainder=normalized_text)
        residence = matched.group("residence")
        return LotParseResult(
            lot=LotNumber(
                block=int(matched.group("block")),
                residence=int(residence) if residence is not None else None,
            ),
            remainder=normalized_text[matched.end() :].lstrip("-"),
        )

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
