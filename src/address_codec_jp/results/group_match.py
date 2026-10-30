from dataclasses import dataclass

from address_codec_jp.address import AddressCode
from address_codec_jp.results.address import AddressMatch


@dataclass(frozen=True, slots=True)
class GroupMatch:
    """
    Result of interpreting addresses that lie in one common area.

    Parameters
    ----------
    area : AddressCode
        Narrowest prefecture, municipality, or town that every address can lie in. The
        area need not be registered, such as an oaza registered only by its chome.
    matches : list[AddressMatch]
        Match of each address within ``area``, in input order.
    """

    area: AddressCode
    matches: list[AddressMatch]
