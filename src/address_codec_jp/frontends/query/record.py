from collections.abc import Callable
from dataclasses import dataclass, field

from address_codec_jp.address import AddressCode
from address_codec_jp.frontends.serialization import JsonValue
from address_codec_jp.results import AddressArea


@dataclass(frozen=True, slots=True)
class QueryRecord:
    """
    Answer to one query, in the forms the front ends write.

    Parameters
    ----------
    fields : dict[str, JsonValue]
        Result fields without the input, as written to JSON.
    build_rows : Callable[[], list[list[str]]]
        Builds the tab-separated rows without the input, on demand so that front ends
        writing JSON skip them; it takes no part in comparison or representation.
    lot_code : AddressCode | None
        Code whose lot record answered a verified ``encode``, a ``locate``, or a
        ``nearest``, or ``None`` when no lot was read.
    areas : tuple[AddressArea, ...]
        Shapes the answer was drawn from.
    """

    fields: dict[str, JsonValue]
    build_rows: Callable[[], list[list[str]]] = field(compare=False, repr=False)
    lot_code: AddressCode | None = None
    areas: tuple[AddressArea, ...] = ()
