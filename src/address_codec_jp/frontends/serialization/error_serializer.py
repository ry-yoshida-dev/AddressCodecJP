from address_codec_jp.errors import AmbiguousAddressError
from address_codec_jp.frontends.serialization.json_value import JsonValue


class ErrorSerializer:
    """Converter of a failed query to JSON-compatible fields."""

    def serialize(self, error: Exception) -> dict[str, JsonValue]:
        """
        Describe an error.

        Parameters
        ----------
        error : Exception
            Raised error.

        Returns
        -------
        dict[str, JsonValue]
            ``error`` message and ``error_type`` name, with the ``candidates`` codes of
            an ``AmbiguousAddressError``.
        """
        fields: dict[str, JsonValue] = {"error": str(error), "error_type": type(error).__name__}
        if isinstance(error, AmbiguousAddressError):
            fields["candidates"] = [str(code) for code in error.candidates]
        return fields
