from typing import ClassVar


class KanjiNumeral:
    """
    Conversion between non-negative integers and kanji numerals.

    Two notations are supported. Positional notation (``二十三``) covers 1 to 9999 and must
    use each of ``千``, ``百``, ``十`` at most once in descending order, without a redundant
    ``一`` before a unit (``一十二`` is rejected; it arises from a name ending in ``一``
    followed by ``十二``). Digit-by-digit
    notation (``一〇二``) uses no unit characters and covers any value. Formatting produces
    positional notation below 10000 and digit-by-digit notation from 10000.
    """

    DIGITS: ClassVar[str] = "〇一二三四五六七八九"
    UNITS: ClassVar[dict[str, int]] = {"千": 1000, "百": 100, "十": 10}
    CHARACTERS: ClassVar[str] = DIGITS + "".join(UNITS)
    POSITIONAL_UPPER_BOUND: ClassVar[int] = 10000

    @classmethod
    def to_int(cls, text: str) -> int:
        """
        Parse a kanji numeral.

        Parameters
        ----------
        text : str
            Kanji numeral such as ``二十三`` or ``一〇二``.

        Returns
        -------
        int
            Parsed value.

        Raises
        ------
        ValueError
            If the text is empty, contains non-numeral characters, or is not a valid
            positional or digit-by-digit numeral (e.g. ``〇十``, ``一二十``, ``十十``,
            ``一十``).
        """
        value = cls.parse(text)
        if value is None:
            raise ValueError(f"Not a valid kanji numeral: {text!r}.")
        return value

    @classmethod
    def parse(cls, text: str) -> int | None:
        """
        Parse a kanji numeral, returning ``None`` for invalid text.

        Parameters
        ----------
        text : str
            Candidate kanji numeral.

        Returns
        -------
        int | None
            Parsed value, or ``None`` when ``to_int`` would raise.
        """
        if not text or any(character not in cls.CHARACTERS for character in text):
            return None
        if not any(character in cls.UNITS for character in text):
            return int("".join(str(cls.DIGITS.index(character)) for character in text))
        total = 0
        previous_unit = cls.POSITIONAL_UPPER_BOUND
        pending_digit: int | None = None
        for character in text:
            unit = cls.UNITS.get(character)
            if unit is None:
                digit = cls.DIGITS.index(character)
                if pending_digit is not None or digit == 0:
                    return None
                pending_digit = digit
                continue
            if unit >= previous_unit or pending_digit == 1:
                return None
            total += (pending_digit or 1) * unit
            previous_unit = unit
            pending_digit = None
        return total + (pending_digit or 0)

    @classmethod
    def from_int(cls, value: int) -> str:
        """
        Format a non-negative integer as a kanji numeral.

        Parameters
        ----------
        value : int
            Value to format.

        Returns
        -------
        str
            Positional numeral such as ``二十三`` below 10000, or digit-by-digit numeral
            such as ``一二三四五`` from 10000.

        Raises
        ------
        ValueError
            If the value is negative.
        """
        if value < 0:
            raise ValueError(f"Value must not be negative, got {value}.")
        if value == 0:
            return cls.DIGITS[0]
        if value >= cls.POSITIONAL_UPPER_BOUND:
            return "".join(cls.DIGITS[int(digit)] for digit in str(value))
        characters: list[str] = []
        for unit_character, unit in cls.UNITS.items():
            digit = value // unit % 10
            if digit > 0:
                characters.append((cls.DIGITS[digit] if digit > 1 else "") + unit_character)
        ones = value % 10
        if ones > 0:
            characters.append(cls.DIGITS[ones])
        return "".join(characters)
