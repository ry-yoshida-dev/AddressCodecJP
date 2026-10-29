import csv
import io
import zipfile
from collections.abc import Iterator
from pathlib import Path


class AbrCsvFile:
    """
    CSV file of the Address Base Registry, either plain or in a ZIP archive.

    Parameters
    ----------
    path : Path
        ``.csv`` file, or ``.zip`` archive whose first CSV member is read.
    """

    def __init__(self, path: Path) -> None:
        self._path: Path = path

    def read_rows(self) -> Iterator[list[str]]:
        """
        Read the rows of the file.

        Yields
        ------
        list[str]
            Header row first, then each data row. Blank lines are skipped.

        Raises
        ------
        FileNotFoundError
            If the file does not exist.
        ValueError
            If the archive has no CSV file.
        """
        if not self._path.is_file():
            raise FileNotFoundError(f"Registry file not found: {self._path}.")
        if zipfile.is_zipfile(self._path):
            with zipfile.ZipFile(self._path) as archive:
                csv_names = [name for name in archive.namelist() if name.endswith(".csv")]
                if not csv_names:
                    raise ValueError(f"No CSV file found in {self._path}.")
                with archive.open(csv_names[0]) as binary_stream:
                    member_stream = io.TextIOWrapper(binary_stream, "utf-8-sig", newline="")
                    yield from (row for row in csv.reader(member_stream) if row)
        else:
            with self._path.open(encoding="utf-8-sig", newline="") as file_stream:
                yield from (row for row in csv.reader(file_stream) if row)
