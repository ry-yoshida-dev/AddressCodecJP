from collections.abc import Callable
from typing import override

from address_codec_jp.frontends.query.text_interpreter import TextInterpreter


class DirectInterpreter(TextInterpreter):
    """
    Interpreter that lets parse errors through unchanged.

    The command line uses it, since every input error is reported alike.
    """

    @override
    def interpret[ValueType](self, parse: Callable[[str], ValueType], text: str) -> ValueType:
        """
        Parse the text as is.

        Parameters
        ----------
        parse : Callable[[str], ValueType]
            Parser of the text.
        text : str
            Input of the query.

        Returns
        -------
        ValueType
            Result of ``parse``.
        """
        return parse(text)
