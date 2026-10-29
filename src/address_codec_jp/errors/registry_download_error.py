from address_codec_jp.errors.address_codec_error import AddressCodecError


class RegistryDownloadError(AddressCodecError, OSError):
    """A registry file could not be downloaded."""
