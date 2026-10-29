import os
from dataclasses import dataclass
from pathlib import Path
from typing import Self


@dataclass(frozen=True, slots=True)
class FileSignature:
    """
    Identity and state of a file, to notice that it was replaced or modified.

    Parameters
    ----------
    device : int
        Device of the file.
    inode : int
        Inode of the file; a file replaced by ``os.replace`` gets another one.
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
    def of(cls, path: Path) -> Self:
        """
        Read the signature of a file.

        Parameters
        ----------
        path : Path
            Existing file.

        Returns
        -------
        Self
            Current signature.

        Raises
        ------
        FileNotFoundError
            If the file does not exist.
        """
        status = os.stat(path)
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
            Signature to compare.

        Returns
        -------
        bool
            ``True`` when the device and inode are equal.
        """
        return self.device == other.device and self.inode == other.inode
