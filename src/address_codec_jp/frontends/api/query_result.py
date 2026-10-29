from dataclasses import dataclass

from address_codec_jp.frontends.api.data_attribution import DataAttribution
from address_codec_jp.frontends.serialization import JsonValue


@dataclass(frozen=True, slots=True)
class QueryResult:
    """
    Result fields of one query and the datasets they were derived from.

    Parameters
    ----------
    fields : dict[str, JsonValue]
        Result fields without the input.
    attributions : frozenset[DataAttribution]
        Datasets to credit.
    """

    fields: dict[str, JsonValue]
    attributions: frozenset[DataAttribution]
