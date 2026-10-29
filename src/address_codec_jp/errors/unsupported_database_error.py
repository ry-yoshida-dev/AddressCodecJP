from address_codec_jp.errors.address_codec_error import AddressCodecError


class UnsupportedDatabaseError(AddressCodecError, ValueError):
    """A database file was not created by this version of AddressCodecJP."""
