from dataclasses import dataclass

from address_codec_jp.text.formatting.digit_width import DigitWidth
from address_codec_jp.text.formatting.lot_style import LotStyle
from address_codec_jp.text.formatting.name_script import NameScript
from address_codec_jp.text.formatting.numeral_style import NumeralStyle


@dataclass(frozen=True, slots=True)
class AddressFormat:
    """
    Output format of a decoded address.

    Parameters
    ----------
    numeral_style : NumeralStyle
        Arabic or kanji numerals for chome and lot numbers.
    lot_style : LotStyle
        ``番``/``号``, ``番地``, or hyphen notation. ``AUTOMATIC`` follows the numbering
        system of the town.
    digit_width : DigitWidth
        Half-width or full-width digits and hyphens.
    is_prefecture_included : bool
        Whether the prefecture name is written.
    is_county_included : bool
        Whether the county name is written.
    name_script : NameScript
        Registered names or their katakana readings.
    is_postal_code_included : bool
        Whether the registered postal code of the town is written first, as in
        ``〒100-0005 東京都千代田区丸の内1丁目``. It is written only for a town with
        exactly one registered postal code, not for prefecture or municipality codes.
    """

    numeral_style: NumeralStyle = NumeralStyle.ARABIC
    lot_style: LotStyle = LotStyle.AUTOMATIC
    digit_width: DigitWidth = DigitWidth.HALF
    is_prefecture_included: bool = True
    is_county_included: bool = True
    name_script: NameScript = NameScript.KANJI
    is_postal_code_included: bool = False
