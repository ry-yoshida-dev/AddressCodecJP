from dataclasses import dataclass

from address_codec_jp.formatting.digit_width import DigitWidth
from address_codec_jp.formatting.lot_style import LotStyle
from address_codec_jp.formatting.numeral_style import NumeralStyle


@dataclass(frozen=True, slots=True)
class AddressFormat:
    """
    Output format of a decoded address.

    Parameters
    ----------
    numeral_style : NumeralStyle
        Arabic or kanji numerals for chome and lot numbers.
    lot_style : LotStyle
        ``番``/``号``, ``番地``, or hyphen notation.
    digit_width : DigitWidth
        Half-width or full-width digits and hyphens.
    is_prefecture_included : bool
        Whether the prefecture name is written.
    is_county_included : bool
        Whether the county name is written.
    """

    numeral_style: NumeralStyle = NumeralStyle.ARABIC
    lot_style: LotStyle = LotStyle.RESIDENCE_INDICATION
    digit_width: DigitWidth = DigitWidth.HALF
    is_prefecture_included: bool = True
    is_county_included: bool = True
