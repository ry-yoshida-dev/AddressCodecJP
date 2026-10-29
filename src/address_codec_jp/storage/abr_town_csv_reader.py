import csv
import io
import re
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import ClassVar, TextIO

from address_codec_jp.domain.town import Town
from address_codec_jp.normalization.kanji_numeral import KanjiNumeral


class AbrTownCsvReader:
    """
    Reader for the town master (町字マスター) CSV of the Address Base Registry.

    Both a plain ``.csv`` file and a ``.zip`` archive containing one CSV file are accepted.
    Columns are looked up by their header names, so extra columns are ignored.
    """

    REQUIRED_COLUMNS: ClassVar[tuple[str, ...]] = (
        "lg_code",
        "machiaza_id",
        "pref",
        "county",
        "city",
        "ward",
        "oaza_cho",
        "chome",
        "koaza",
    )
    _CHOME: ClassVar[re.Pattern[str]] = re.compile(
        f"(?P<number>[0-9０-９]+|[{KanjiNumeral.CHARACTERS}]+)丁目?"
    )

    def read(self, path: Path) -> Iterator[Town]:
        """
        Read towns from a town master file.

        Parameters
        ----------
        path : Path
            Path to ``mt_town_all.csv`` or a ZIP archive containing it.

        Yields
        ------
        Town
            Town record for each CSV row.

        Raises
        ------
        FileNotFoundError
            If the file does not exist.
        ValueError
            If the archive has no CSV file, required columns are missing, a row is short,
            or a code is malformed.
        """
        if not path.is_file():
            raise FileNotFoundError(f"Town master file not found: {path}.")
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as archive:
                csv_names = [name for name in archive.namelist() if name.endswith(".csv")]
                if not csv_names:
                    raise ValueError(f"No CSV file found in {path}.")
                with archive.open(csv_names[0]) as binary_stream:
                    yield from self._read_stream(io.TextIOWrapper(binary_stream, "utf-8-sig"))
        else:
            with path.open(encoding="utf-8-sig", newline="") as text_stream:
                yield from self._read_stream(text_stream)

    def _read_stream(self, stream: TextIO) -> Iterator[Town]:
        rows = csv.reader(stream)
        header = next(rows, None)
        if header is None:
            raise ValueError("Town master CSV is empty.")
        missing_columns = [column for column in self.REQUIRED_COLUMNS if column not in header]
        if missing_columns:
            raise ValueError(f"Town master CSV lacks required columns: {missing_columns}.")
        column_index = {column: header.index(column) for column in self.REQUIRED_COLUMNS}
        for row in rows:
            if not row:
                continue
            if len(row) < len(header):
                raise ValueError(
                    f"Line {rows.line_num} has {len(row)} columns, expected {len(header)}."
                )
            chome_name = row[column_index["chome"]]
            yield Town(
                lg_code=row[column_index["lg_code"]].zfill(6),
                machiaza_id=row[column_index["machiaza_id"]].zfill(7),
                prefecture_name=row[column_index["pref"]],
                county_name=row[column_index["county"]],
                city_name=row[column_index["city"]],
                ward_name=row[column_index["ward"]],
                oaza_name=row[column_index["oaza_cho"]],
                chome_name=chome_name,
                chome_number=self._parse_chome_number(chome_name),
                koaza_name=row[column_index["koaza"]],
            )

    def _parse_chome_number(self, chome_name: str) -> int | None:
        matched = self._CHOME.fullmatch(chome_name)
        if matched is None:
            return None
        number = matched.group("number")
        if number[0] in KanjiNumeral.CHARACTERS:
            return KanjiNumeral.to_int(number)
        return int(number)
