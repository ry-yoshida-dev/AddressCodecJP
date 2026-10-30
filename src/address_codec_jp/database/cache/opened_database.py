import weakref
from dataclasses import dataclass

from address_codec_jp.database.cache.file_signature import DatabaseFileSignature
from address_codec_jp.database.storage import AddressDatabase


@dataclass(frozen=True, slots=True)
class OpenedDatabase:
    """
    Database that a cache opened for a codec, and the file it was opened on.

    Parameters
    ----------
    database : weakref.ref[AddressDatabase]
        Opened database, held weakly so that a discarded codec is forgotten.
    signature : DatabaseFileSignature
        Signature of the file when it was opened.
    """

    database: weakref.ref[AddressDatabase]
    signature: DatabaseFileSignature

    @property
    def is_open(self) -> bool:
        """
        Tell whether the database is still in use.

        Returns
        -------
        bool
            ``True`` unless the database has been closed or discarded.
        """
        database = self.database()
        return database is not None and not database.is_closed
