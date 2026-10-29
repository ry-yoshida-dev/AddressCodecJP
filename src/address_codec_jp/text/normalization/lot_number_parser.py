import re
from typing import ClassVar

from address_codec_jp.address import LotNumber
from address_codec_jp.text.normalization.lot_parse_result import LotParseResult


class LotNumberParser:
    """
    Parser for block and residence numbers in normalized text.

    Accepted notations include ``2番3号``, ``2番地3``, ``2番地の3``, ``2-3`` and ``2の3``.
    """

    _LOT: ClassVar[re.Pattern[str]] = re.compile(
        r"(?P<block>[1-9][0-9]*)(?![0-9丁])(?:番地|番)?(?:[-のノ之]?(?P<residence>[1-9][0-9]*)(?![0-9丁])(?:号|番地|番)?)?"
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
