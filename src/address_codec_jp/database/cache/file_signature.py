from dataclasses import dataclass
from pathlib import Path
from typing import Self


@dataclass(frozen=True, slots=True)
class DatabaseFileSignature:
    """
    Identity and state of a database file, to notice that it was replaced or modified.

    Parameters
    ----------
    device : int
        Device of the file.
    inode : int
        Inode of the file; a file replaced by a rename or rebuilt after a deletion gets
        another one while the old one is still open.
    modified_ns : int
        Last modification time in nanoseconds.
    size_bytes : int
        Size of the file.
    """

    device: int
    inode: int
    modified_ns: int
    size_bytes: int

    @classmethod
    def of(cls, path: Path) -> Self | None:
        """
        Read the signature of a file.

        Parameters
        ----------
        path : Path
            File to inspect.

        Returns
        -------
        Self | None
            Current signature, or ``None`` when the file does not exist.
        """
        if not path.is_file():
            return None
        status = path.stat()
        return cls(
            device=status.st_dev,
            inode=status.st_ino,
            modified_ns=status.st_mtime_ns,
            size_bytes=status.st_size,
        )

    def is_same_file(self, other: Self) -> bool:
        """
        Tell whether two signatures belong to the same file, modified or not.

        Parameters
        ----------
        other : Self
            Signature to compare with.

        Returns
        -------
        bool
            ``True`` when device and inode agree.
        """
        return self.device == other.device and self.inode == other.inode
