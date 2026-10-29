from address_codec_jp.errors.address_codec_error import AddressCodecError


class PositionNotFoundError(AddressCodecError, LookupError):
    """No imported representative point fits the address or coordinate."""
