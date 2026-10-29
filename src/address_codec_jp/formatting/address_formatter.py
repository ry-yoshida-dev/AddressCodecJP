from typing import ClassVar

from address_codec_jp.domain.address import Address
from address_codec_jp.domain.lot_number import LotNumber
from address_codec_jp.domain.municipality import Municipality
from address_codec_jp.domain.town import Town
from address_codec_jp.errors.reading_not_found_error import ReadingNotFoundError
from address_codec_jp.formatting.address_format import AddressFormat
from address_codec_jp.formatting.digit_width import DigitWidth
from address_codec_jp.formatting.lot_style import LotStyle
from address_codec_jp.formatting.name_script import NameScript
from address_codec_jp.formatting.numeral_style import NumeralStyle
from address_codec_jp.normalization.kanji_numeral import KanjiNumeral


class AddressFormatter:
    """Renderer of prefectures, municipalities, and towns as address text."""

    _FULL_WIDTH_TABLE: ClassVar[dict[int, int]] = str.maketrans(
        "0123456789-", "０１２３４５６７８９－"
    )
    _HALF_WIDTH_TABLE: ClassVar[dict[int, int]] = str.maketrans(
        "０１２３４５６７８９", "0123456789"
    )
    _SHORT_CHOME_MARKER: ClassVar[str] = "丁"

    def format(self, address: Address, address_format: AddressFormat) -> str:
        """
        Render an address.

        Parameters
        ----------
        address : Address
            Address to render.
        address_format : AddressFormat
            Output format. A prefecture alone is written even when the format excludes
            the prefecture, and the postal code is written only for towns.

        Returns
        -------
        str
            Address text such as ``東京都台東区浅草橋1丁目2番3号``.

        Raises
        ------
        ReadingNotFoundError
            If katakana is requested and the registry has no reading of a name.
        """
        if address.town is not None:
            text = (
                self._postal_code_text(address.town, address_format)
                + self._municipality_text(address.town.municipality, address_format)
                + self._name(address.town.oaza_name, address.town.oaza_kana, address_format)
                + self._format_numbers(address.town, address.lot, address_format)
            )
        elif address.municipality is not None:
            text = self._municipality_text(address.municipality, address_format)
        else:
            text = self._name(address.prefecture.name, address.prefecture.kana, address_format)
        return self._apply_width(text, address_format)

    def _postal_code_text(self, town: Town, address_format: AddressFormat) -> str:
        match town.postal_codes:
            case (postal_code,) if address_format.is_postal_code_included:
                return f"〒{postal_code[:3]}-{postal_code[3:]} "
            case _:
                return ""

    def _municipality_text(self, municipality: Municipality, address_format: AddressFormat) -> str:
        parts: list[str] = []
        if address_format.is_prefecture_included:
            parts.append(
                self._name(
                    municipality.prefecture_name, municipality.prefecture_kana, address_format
                )
            )
        if address_format.is_county_included:
            parts.append(
                self._name(municipality.county_name, municipality.county_kana, address_format)
            )
        parts.extend(
            [
                self._name(municipality.city_name, municipality.city_kana, address_format),
                self._name(municipality.ward_name, municipality.ward_kana, address_format),
            ]
        )
        return "".join(parts)

    def _name(self, name: str, kana: str, address_format: AddressFormat) -> str:
        match address_format.name_script:
            case NameScript.KANJI:
                return name
            case NameScript.KATAKANA:
                if name and not kana:
                    raise ReadingNotFoundError(f"The registry has no reading of {name!r}.")
                return kana

    def _apply_width(self, text: str, address_format: AddressFormat) -> str:
        match address_format.digit_width:
            case DigitWidth.HALF:
                return text.translate(self._HALF_WIDTH_TABLE)
            case DigitWidth.FULL:
                return text.translate(self._FULL_WIDTH_TABLE)

    def _format_numbers(self, town: Town, lot: LotNumber, address_format: AddressFormat) -> str:
        lot_numbers = [self._format_numeral(number, address_format) for number in lot.numbers]
        is_chome_hyphenated = (
            address_format.lot_style is LotStyle.HYPHEN
            and town.chome_number is not None
            and not town.koaza_name
            and bool(lot_numbers)
        )
        if is_chome_hyphenated and town.chome_number is not None:
            return "-".join([self._format_numeral(town.chome_number, address_format), *lot_numbers])
        return (
            self._format_chome(town, address_format)
            + self._name(town.koaza_name, town.koaza_kana, address_format)
            + self._format_lot(lot_numbers, address_format)
        )

    def _format_chome(self, town: Town, address_format: AddressFormat) -> str:
        if town.chome_number is None:
            return self._name(town.chome_name, town.chome_kana, address_format)
        is_short = town.chome_name.endswith(self._SHORT_CHOME_MARKER)
        match address_format.name_script, is_short:
            case NameScript.KANJI, True:
                suffix = "丁"
            case NameScript.KANJI, False:
                suffix = "丁目"
            case NameScript.KATAKANA, True:
                suffix = "チョウ"
            case NameScript.KATAKANA, False:
                suffix = "チョウメ"
        return self._format_numeral(town.chome_number, address_format) + suffix

    def _format_lot(self, lot_numbers: list[str], address_format: AddressFormat) -> str:
        block_marker, residence_marker, parcel_marker = self._lot_markers(
            address_format.name_script
        )
        match address_format.lot_style, lot_numbers:
            case _, []:
                return ""
            case LotStyle.RESIDENCE_INDICATION, [block]:
                return f"{block}{block_marker}"
            case LotStyle.RESIDENCE_INDICATION, [block, residence]:
                return f"{block}{block_marker}{residence}{residence_marker}"
            case LotStyle.LAND_PARCEL, [block]:
                return f"{block}{parcel_marker}"
            case LotStyle.LAND_PARCEL, [block, residence]:
                return f"{block}{parcel_marker}{residence}"
            case LotStyle.HYPHEN, _:
                return "-".join(lot_numbers)
            case _:
                raise ValueError(f"Unsupported lot numbers: {lot_numbers}.")

    def _lot_markers(self, name_script: NameScript) -> tuple[str, str, str]:
        match name_script:
            case NameScript.KANJI:
                return "番", "号", "番地"
            case NameScript.KATAKANA:
                return "バン", "ゴウ", "バンチ"

    def _format_numeral(self, number: int, address_format: AddressFormat) -> str:
        match address_format.numeral_style:
            case NumeralStyle.ARABIC:
                return str(number)
            case NumeralStyle.KANJI:
                return KanjiNumeral.from_int(number)
