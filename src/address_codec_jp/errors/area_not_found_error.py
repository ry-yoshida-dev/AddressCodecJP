from address_codec_jp.errors.address_codec_error import AddressCodecError


class AreaNotFoundError(AddressCodecError, LookupError):
    """No imported area shape fits the address."""
