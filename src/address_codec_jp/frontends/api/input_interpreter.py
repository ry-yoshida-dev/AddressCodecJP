from collections.abc import Callable

from address_codec_jp.errors import AddressCodecError
from address_codec_jp.frontends.api.invalid_request_error import InvalidRequestError


class InputInterpreter:
    """
    Parser of request inputs that reports malformed ones as ``InvalidRequestError``.

    Only a ``ValueError`` raised while interpreting the text is blamed on the request.
    A library error deriving from ``ValueError``, such as ``RegistryFormatError`` or
    ``UnsupportedDatabaseError``, is a fault of the server and passes through, as does
    any ``ValueError`` raised outside an interpretation.
    """

    def interpret[ValueType](self, parse: Callable[[str], ValueType], text: str) -> ValueType:
        """
        Interpret a request value.

        Parameters
        ----------
        parse : Callable[[str], ValueType]
            Parser of the value.
        text : str
            Value given in the request.

        Returns
        -------
        ValueType
            Result of ``parse``.

        Raises
        ------
        InvalidRequestError
            If ``parse`` rejects the text with a ``ValueError``.
        """
        try:
            return parse(text)
        except AddressCodecError:
            raise
        except ValueError as error:
            raise InvalidRequestError(str(error)) from error
