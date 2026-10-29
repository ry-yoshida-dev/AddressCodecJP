import re
from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True, slots=True)
class Prefecture:
    """
    Prefecture identified by a two-digit prefecture code.

    Parameters
    ----------
    code : str
        Two-digit prefecture code from ``01`` to ``47``, e.g. ``13``.
    name : str
        Prefecture name, e.g. ``東京都``.
    kana : str
        Katakana reading of the name, e.g. ``トウキョウト``, or an empty string when the
        registry has none.

    Raises
    ------
    ValueError
        If ``code`` is not a prefecture code.
    """

    _CODE: ClassVar[re.Pattern[str]] = re.compile(r"0[1-9]|[1-3][0-9]|4[0-7]")

    code: str
    name: str
    kana: str

    def __post_init__(self) -> None:
        if not self.is_code(self.code):
            raise ValueError(f"Prefecture code must be 01 to 47, got {self.code!r}.")

    @classmethod
    def is_code(cls, text: str) -> bool:
        """
        Tell whether a text is a two-digit prefecture code.

        Parameters
        ----------
        text : str
            Candidate code.

        Returns
        -------
        bool
            ``True`` for ``01`` to ``47``.
        """
        return cls._CODE.fullmatch(text) is not None
