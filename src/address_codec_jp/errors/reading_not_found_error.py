from address_codec_jp.errors.address_codec_error import AddressCodecError


class ReadingNotFoundError(AddressCodecError, LookupError):
    """The registry has no katakana reading of a name that is to be written."""
