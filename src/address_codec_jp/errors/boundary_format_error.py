from address_codec_jp.errors.address_codec_error import AddressCodecError


class BoundaryFormatError(AddressCodecError, ValueError):
    """A census boundary or registry map file is malformed."""
