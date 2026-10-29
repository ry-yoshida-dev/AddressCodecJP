from typing import ClassVar

from address_codec_jp.domain.lot_number import LotNumber
from address_codec_jp.domain.municipality import Municipality
from address_codec_jp.domain.prefecture import Prefecture
from address_codec_jp.domain.town import Town
from address_codec_jp.formatting.address_format import AddressFormat
from address_codec_jp.formatting.digit_width import DigitWidth
from address_codec_jp.formatting.lot_style import LotStyle
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

    def format_prefecture(self, prefecture: Prefecture) -> str:
        """
        Render a prefecture.

        Parameters
        ----------
        prefecture : Prefecture
            Prefecture to render.

        Returns
        -------
        str
            Prefecture name. It is always written regardless of the format.
        """
        return prefecture.name

    def format_municipality(self, municipality: Municipality, address_format: AddressFormat) -> str:
        """
        Render a municipality.

        Parameters
        ----------
        municipality : Municipality
            Municipality to render.
        address_format : AddressFormat
            Output format.

        Returns
        -------
        str
            Address text such as ``東京都台東区``.
        """
        return self._apply_width(
            self._municipality_text(municipality, address_format), address_format
        )

    def format_town(self, town: Town, lot: LotNumber, address_format: AddressFormat) -> str:
        """
        Render a town with lot numbers.

        Parameters
        ----------
        town : Town
            Town to render.
        lot : LotNumber
            Block and residence numbers.
        address_format : AddressFormat
            Output format.

        Returns
        -------
        str
            Address text such as ``東京都台東区浅草橋1丁目2番3号``.
        """
        text = (
            self._municipality_text(town.municipality, address_format)
            + town.oaza_name
            + self._format_numbers(town, lot, address_format)
        )
        return self._apply_width(text, address_format)

    def _municipality_text(self, municipality: Municipality, address_format: AddressFormat) -> str:
        parts: list[str] = []
        if address_format.is_prefecture_included:
            parts.append(municipality.prefecture_name)
        if address_format.is_county_included:
            parts.append(municipality.county_name)
        parts.extend([municipality.city_name, municipality.ward_name])
        return "".join(parts)

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
            + town.koaza_name
            + self._format_lot(lot_numbers, address_format.lot_style)
        )

    def _format_chome(self, town: Town, address_format: AddressFormat) -> str:
        if town.chome_number is None:
            return town.chome_name
        suffix = "丁" if town.chome_name.endswith("丁") else "丁目"
        return self._format_numeral(town.chome_number, address_format) + suffix

    def _format_lot(self, lot_numbers: list[str], lot_style: LotStyle) -> str:
        match lot_style, lot_numbers:
            case _, []:
                return ""
            case LotStyle.RESIDENCE_INDICATION, [block]:
                return f"{block}番"
            case LotStyle.RESIDENCE_INDICATION, [block, residence]:
                return f"{block}番{residence}号"
            case LotStyle.LAND_PARCEL, [block]:
                return f"{block}番地"
            case LotStyle.LAND_PARCEL, [block, residence]:
                return f"{block}番地{residence}"
            case LotStyle.HYPHEN, _:
                return "-".join(lot_numbers)
            case _:
                raise ValueError(f"Unsupported lot numbers: {lot_numbers}.")

    def _format_numeral(self, number: int, address_format: AddressFormat) -> str:
        match address_format.numeral_style:
            case NumeralStyle.ARABIC:
                return str(number)
            case NumeralStyle.KANJI:
                return KanjiNumeral.from_int(number)
