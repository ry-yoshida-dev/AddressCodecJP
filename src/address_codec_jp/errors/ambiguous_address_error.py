from address_codec_jp.address import AddressCode
from address_codec_jp.errors.address_codec_error import AddressCodecError


class AmbiguousAddressError(AddressCodecError, LookupError):
    """
    An address fits several registered areas or lot numbers equally well.

    Parameters
    ----------
    message : str
        Description of the ambiguity.
    candidates : tuple[AddressCode, ...]
        Codes the address may stand for, in ascending order.
    """

    def __init__(self, message: str, candidates: tuple[AddressCode, ...]) -> None:
        super().__init__(message)
        self.candidates: tuple[AddressCode, ...] = candidates
