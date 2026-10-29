import csv
import io
import zipfile
from collections.abc import Iterator
from pathlib import Path

from address_codec_jp.errors.registry_format_error import RegistryFormatError
from address_codec_jp.registry.abr_csv_row import AbrCsvRow
from address_codec_jp.registry.abr_dataset import AbrDataset


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

    def detect_dataset(self) -> AbrDataset:
        """
        Identify the dataset of the file by its header.

        Returns
        -------
        AbrDataset
            Dataset of the file. Files may be renamed, since the name is not consulted.

        Raises
        ------
        FileNotFoundError
            If the file does not exist.
        RegistryFormatError
            If the file is empty or belongs to none of the datasets.
        """
        rows = self._read_rows()
        header = next(rows, None)
        if header is None:
            raise RegistryFormatError(f"Registry CSV {self._path} is empty.")
        return AbrDataset.detect(header, next(rows, None))

    def read_records(self, dataset: AbrDataset) -> Iterator[AbrCsvRow]:
        """
        Read the data rows of the file as a dataset.

        Parameters
        ----------
        dataset : AbrDataset
            Dataset whose required columns are read.

        Yields
        ------
        AbrCsvRow
            Each data row with the required columns. Blank lines are skipped.

        Raises
        ------
        FileNotFoundError
            If the file does not exist.
        RegistryFormatError
            If the file is empty, the archive has no CSV file, required columns are
            missing, or a row is short. The message names the row.
        """
        rows = self._read_rows()
        header = next(rows, None)
        if header is None:
            raise RegistryFormatError(f"Registry CSV {self._path} is empty.")
        missing_columns = [column for column in dataset.required_columns if column not in header]
        if missing_columns:
            raise RegistryFormatError(
                f"{dataset.value} CSV {self._path} lacks required columns: {missing_columns}."
            )
        column_index = {column: header.index(column) for column in dataset.required_columns}
        for row_number, row in enumerate(rows, start=2):
            if len(row) < len(header):
                raise RegistryFormatError(
                    f"Row {row_number} has {len(row)} columns, expected {len(header)}."
                )
            yield AbrCsvRow(
                number=row_number,
                values={column: row[index] for column, index in column_index.items()},
            )

    def _read_rows(self) -> Iterator[list[str]]:
        if not self._path.is_file():
            raise FileNotFoundError(f"Registry file not found: {self._path}.")
        if zipfile.is_zipfile(self._path):
            with zipfile.ZipFile(self._path) as archive:
                csv_names = [name for name in archive.namelist() if name.endswith(".csv")]
                if not csv_names:
                    raise RegistryFormatError(f"No CSV file found in {self._path}.")
                with archive.open(csv_names[0]) as binary_stream:
                    member_stream = io.TextIOWrapper(binary_stream, "utf-8-sig", newline="")
                    yield from (row for row in csv.reader(member_stream) if row)
        else:
            with self._path.open(encoding="utf-8-sig", newline="") as file_stream:
                yield from (row for row in csv.reader(file_stream) if row)
