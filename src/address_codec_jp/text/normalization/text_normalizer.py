import re
import unicodedata
from typing import ClassVar

from address_codec_jp.text.normalization.kanji_numeral import KanjiNumeral


class TextNormalizer:
    """
    Canonical text forms used to compare addresses with registry names.

    ``normalize`` produces the strict form: width, whitespace, postal code, dash, and
    kanji numeral variants are unified, and a dash after katakana becomes the long vowel
    ``ー`` (``流通センタ－`` equals ``流通センター``). A kanji numeral run that is valid only
    without its leading ``一`` keeps that ``一`` as part of the preceding name
    (``九ノ一十二番`` becomes ``9ノ一12番``). Characters that the registry uses to
    tell towns apart are kept. ``fold`` additionally unifies ``ヶ``/``ケ``/``が``,
    ``の``/``ノ``/``之`` and old-style kanji for a loose comparison. Folding keeps the
    text length, so positions in the strict and folded forms correspond.
    """

    _KANJI: ClassVar[str] = "㐀-鿿豈-﫿々"
    _NUMERALS: ClassVar[str] = "0-9" + KanjiNumeral.CHARACTERS
    _VARIANT_TABLE: ClassVar[dict[int, str]] = str.maketrans(
        {
            "舘": "館",
            "澤": "沢",
            "冨": "富",
            "嶋": "島",
            "嶌": "島",
            "﨑": "崎",
            "髙": "高",
            "邊": "辺",
            "邉": "辺",
            "槇": "槙",
            "渕": "淵",
            "廣": "広",
            "濱": "浜",
            "檜": "桧",
            "驒": "騨",
        }
    )
    _POSTAL_CODE: ClassVar[re.Pattern[str]] = re.compile(
        r"^〒?(?P<head>[0-9]{3})-?(?P<tail>[0-9]{4})"
    )
    _WHITESPACE: ClassVar[re.Pattern[str]] = re.compile(r"\s+")
    _WHITESPACE_BETWEEN_DIGITS: ClassVar[re.Pattern[str]] = re.compile(r"(?<=[0-9])\s+(?=[0-9])")
    _KE_VARIANTS: ClassVar[re.Pattern[str]] = re.compile(
        f"(?<=[{_KANJI}0-9])[ヶヵケが](?=[{_KANJI}0-9])"
    )
    _NO_VARIANTS: ClassVar[re.Pattern[str]] = re.compile(
        f"(?<=[{_KANJI}0-9])[のノ之](?=[{_KANJI}0-9])"
    )
    _DASH_VARIANTS: ClassVar[re.Pattern[str]] = re.compile("[‐‑‒–—―−﹣－⁃]")
    _LONG_VOWEL_DASH: ClassVar[re.Pattern[str]] = re.compile(
        f"(?<=[{_NUMERALS}])[ーｰ](?=[{_NUMERALS}])"
    )
    _KANJI_ONE_DASH: ClassVar[re.Pattern[str]] = re.compile("(?<=[0-9])一(?=[0-9])")
    _KATAKANA_LONG_VOWEL: ClassVar[re.Pattern[str]] = re.compile("(?<=[ァ-ヴ])-")
    _KANJI_NUMBER: ClassVar[re.Pattern[str]] = re.compile(
        f"[{KanjiNumeral.CHARACTERS}]+(?=丁目|丁|番|号|条|線|地割|の|ノ|-)"
    )
    _TRAILING_KANJI_NUMBER: ClassVar[re.Pattern[str]] = re.compile(f"[{KanjiNumeral.CHARACTERS}]+$")
    _NAME_ENDING_NUMERAL: ClassVar[str] = "一"
    _REPEATED_DASH: ClassVar[re.Pattern[str]] = re.compile("-{2,}")

    def normalize(self, text: str) -> str:
        """
        Normalize address text into the strict form.

        Parameters
        ----------
        text : str
            Raw address or registry name.

        Returns
        -------
        str
            Normalized text.
        """
        return self._normalize(text, is_trailing_number_converted=True)

    def extract_postal_code(self, text: str) -> str | None:
        """
        Read the postal code that ``normalize`` removes from the start of an address.

        Parameters
        ----------
        text : str
            Raw address, e.g. ``〒100-0005 東京都千代田区丸の内``.

        Returns
        -------
        str | None
            Seven-digit postal code, or ``None`` when the address does not start with one.
        """
        prepared = unicodedata.normalize("NFKC", text)
        prepared = self._WHITESPACE_BETWEEN_DIGITS.sub("-", prepared)
        prepared = self._normalize_dashes(self._WHITESPACE.sub("", prepared))
        matched = self._POSTAL_CODE.match(prepared)
        if matched is None:
            return None
        return matched.group("head") + matched.group("tail")

    def parse_postal_code(self, text: str) -> str:
        """
        Read a postal code written on its own.

        Parameters
        ----------
        text : str
            Postal code such as ``100-0005``, ``〒1000005``, or ``１００－０００５``.

        Returns
        -------
        str
            Seven-digit postal code.

        Raises
        ------
        ValueError
            If the text is not a postal code.
        """
        prepared = self._normalize_dashes(
            self._WHITESPACE.sub("", unicodedata.normalize("NFKC", text))
        )
        matched = self._POSTAL_CODE.fullmatch(prepared)
        if matched is None:
            raise ValueError(f"Invalid postal code: {text!r}.")
        return matched.group("head") + matched.group("tail")

    def normalize_name(self, name: str) -> set[str]:
        """
        Normalize a registry name into every strict form it can take inside an address.

        A trailing kanji numeral, as in ``九ノ一``, is converted when the name ends the
        address but kept when lot numbers follow it, so both forms are returned.

        Parameters
        ----------
        name : str
            Registry name such as an oaza or koaza name.

        Returns
        -------
        set[str]
            One or two normalized forms.
        """
        return {
            self._normalize(name, is_trailing_number_converted=True),
            self._normalize(name, is_trailing_number_converted=False),
        }

    def _normalize(self, text: str, *, is_trailing_number_converted: bool) -> str:
        normalized = unicodedata.normalize("NFKC", text)
        normalized = self._WHITESPACE_BETWEEN_DIGITS.sub("-", normalized)
        normalized = self._WHITESPACE.sub("", normalized)
        normalized = self._normalize_dashes(normalized)
        normalized = self._POSTAL_CODE.sub("", normalized)
        normalized = self._convert_kanji_numbers(
            normalized, is_trailing_number_converted=is_trailing_number_converted
        )
        normalized = self._normalize_dashes(normalized)
        return self._REPEATED_DASH.sub("-", normalized).strip("-")

    def fold(self, normalized_text: str) -> str:
        """
        Fold notation variants of strictly normalized text for a loose comparison.

        Parameters
        ----------
        normalized_text : str
            Text returned by ``normalize``.

        Returns
        -------
        str
            Folded text of the same length.
        """
        folded = normalized_text.translate(self._VARIANT_TABLE)
        folded = self._KE_VARIANTS.sub("ケ", folded)
        return self._NO_VARIANTS.sub("の", folded)

    def _convert_kanji_numbers(self, text: str, *, is_trailing_number_converted: bool) -> str:
        patterns = [self._KANJI_NUMBER]
        if is_trailing_number_converted:
            patterns.append(self._TRAILING_KANJI_NUMBER)
        for pattern in patterns:
            text = pattern.sub(self._replace_kanji_number, text)
        return text

    def _replace_kanji_number(self, matched: re.Match[str]) -> str:
        text = matched.group()
        value = KanjiNumeral.parse(text)
        if value is not None:
            return str(value)
        name_ending = text[:1]
        number_value = KanjiNumeral.parse(text[1:])
        if name_ending == self._NAME_ENDING_NUMERAL and number_value is not None:
            return name_ending + str(number_value)
        return text

    def _normalize_dashes(self, text: str) -> str:
        text = self._DASH_VARIANTS.sub("-", text)
        text = self._KATAKANA_LONG_VOWEL.sub("ー", text)
        text = self._LONG_VOWEL_DASH.sub("-", text)
        return self._KANJI_ONE_DASH.sub("-", text)
