from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Prefecture:
    """
    Prefecture identified by a two-digit prefecture code.

    Parameters
    ----------
    code : str
        Two-digit prefecture code, e.g. ``13``.
    name : str
        Prefecture name, e.g. ``東京都``.
    kana : str
        Katakana reading of the name, e.g. ``トウキョウト``, or an empty string when the
        registry has none.
    """

    code: str
    name: str
    kana: str
