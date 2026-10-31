from dataclasses import dataclass

from address_codec_jp.address import AddressCode


@dataclass(frozen=True, slots=True)
class RenderedAddress:
    """
    Address code with the address rendered from it.

    ``ResultSerializer.render`` creates it once, so that the JSON fields and the
    tab-separated rows of a result share one rendering.

    Parameters
    ----------
    code : AddressCode
        Code of the address.
    address : str
        Address rendered from ``code``.
    """

    code: AddressCode
    address: str
