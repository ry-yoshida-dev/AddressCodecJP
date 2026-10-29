from address_codec_jp.errors.address_codec_error import AddressCodecError


class RegistryFormatError(AddressCodecError, ValueError):
    """A registry file is not the expected dataset or contains malformed rows."""
