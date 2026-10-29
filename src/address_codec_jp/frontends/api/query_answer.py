from dataclasses import dataclass

from address_codec_jp.frontends.serialization import JsonValue


@dataclass(frozen=True, slots=True)
class QueryAnswer:
    """
    Response fields of a query and the credits of the datasets they are derived from.

    Parameters
    ----------
    fields : dict[str, JsonValue]
        Result fields.
    credits : tuple[str, ...]
        Source credits required by the terms of use of the datasets.
    """

    fields: dict[str, JsonValue]
    credits: tuple[str, ...]

    def to_json(self) -> dict[str, JsonValue]:
        """
        Build the response body.

        Returns
        -------
        dict[str, JsonValue]
            ``fields`` followed by ``attribution``, the list of credits.
        """
        credits: list[JsonValue] = list(self.credits)
        return {**self.fields, "attribution": credits}
