from address_codec_jp.errors.address_codec_error import AddressCodecError


class DatasetNotImportedError(AddressCodecError, RuntimeError):
    """A dataset that the operation needs has not been imported into the database."""
