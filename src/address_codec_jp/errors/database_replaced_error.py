from address_codec_jp.errors.dataset_not_imported_error import DatasetNotImportedError


class DatabaseReplacedError(DatasetNotImportedError):
    """
    The cache database was replaced or removed after a codec opened it.

    Data added now would go to a file the codec does not read, such as after
    ``DatabaseCache.refresh`` or ``clear`` in this or another process; close the codec
    and open it again.
    """
