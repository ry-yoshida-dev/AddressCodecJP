from collections.abc import Callable
from typing import Protocol


class TextInterpreter(Protocol):
    """
    Parser wrapper that decides how a front end reports a malformed input.

    ``QueryRunner`` calls ``interpret`` on every text it parses, so that the web API can
    blame malformed input on the request while the command line reports it as is.
    """

    def interpret[ValueType](self, parse: Callable[[str], ValueType], text: str) -> ValueType:
        """
        Interpret the text of a query.

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
        ...
