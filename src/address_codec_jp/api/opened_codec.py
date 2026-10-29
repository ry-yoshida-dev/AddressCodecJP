from dataclasses import dataclass

from address_codec_jp.address_codec import AddressCodec
from address_codec_jp.api.file_signature import FileSignature


@dataclass(frozen=True, slots=True)
class OpenedCodec:
    """
    Codec of a worker thread and the database file it was opened on.

    Parameters
    ----------
    codec : AddressCodec
        Codec bound to the thread that opened it.
    signature : FileSignature
        Signature of the database file when the codec was opened.
    """

    codec: AddressCodec
    signature: FileSignature
