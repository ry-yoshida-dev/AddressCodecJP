from address_codec_jp.errors.address_codec_error import AddressCodecError


class AddressNotFoundError(AddressCodecError, LookupError):
    """An address, code, or lot is not registered in the imported datasets."""
