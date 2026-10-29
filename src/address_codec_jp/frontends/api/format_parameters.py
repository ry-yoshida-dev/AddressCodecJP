from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from address_codec_jp.frontends.api.input_interpreter import InputInterpreter
from address_codec_jp.frontends.serialization import EnumName
from address_codec_jp.text.formatting import (
    AddressFormat,
    DigitWidth,
    LotStyle,
    NameScript,
    NumeralStyle,
)


class FormatParameters(BaseModel):
    """
    Request parameters that choose the format of decoded addresses.

    Enum values are member names in any case, as on the command line.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(populate_by_name=True)

    numeral: str = Field(default="arabic", description="arabic or kanji numerals.")
    lot: str = Field(
        default="automatic",
        description="automatic, residence_indication, land_parcel, or hyphen notation.",
    )
    width: str = Field(default="half", description="half or full width digits.")
    is_prefecture_included: bool = Field(default=True, alias="prefecture")
    is_county_included: bool = Field(default=True, alias="county")
    is_kana: bool = Field(default=False, alias="kana")
    is_postal_code_included: bool = Field(default=False, alias="postal_code")

    def to_address_format(self) -> AddressFormat:
        """
        Build the address format.

        Returns
        -------
        AddressFormat
            Format with the requested options.

        Raises
        ------
        InvalidRequestError
            If an enum value names no member.
        """
        interpreter = InputInterpreter()
        return AddressFormat(
            numeral_style=interpreter.interpret(EnumName(NumeralStyle).parse, self.numeral),
            lot_style=interpreter.interpret(EnumName(LotStyle).parse, self.lot),
            digit_width=interpreter.interpret(EnumName(DigitWidth).parse, self.width),
            is_prefecture_included=self.is_prefecture_included,
            is_county_included=self.is_county_included,
            name_script=NameScript.KATAKANA if self.is_kana else NameScript.KANJI,
            is_postal_code_included=self.is_postal_code_included,
        )
