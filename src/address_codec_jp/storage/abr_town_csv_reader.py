import re
from collections.abc import Iterator
from pathlib import Path
from typing import ClassVar

from address_codec_jp.domain.municipality import Municipality
from address_codec_jp.domain.town import Town
from address_codec_jp.errors.registry_format_error import RegistryFormatError
from address_codec_jp.normalization.kanji_numeral import KanjiNumeral
from address_codec_jp.storage.abr_csv_file import AbrCsvFile
from address_codec_jp.storage.abr_dataset import AbrDataset


class AbrTownCsvReader:
    """
    Reader for the town master (町字マスター) CSV of the Address Base Registry.

    Both a plain ``.csv`` file and a ``.zip`` archive containing one CSV file are accepted.
    Columns are looked up by their header names, so extra columns are ignored. Rows with
    an abolition date (``ablt_date``) are skipped. ``post_code`` may list several postal
    codes separated by ``;``.
    """

    _MUNICIPALITY_COLUMNS: ClassVar[tuple[str, ...]] = (
        "lg_code",
        "pref",
        "county",
        "city",
        "ward",
        "pref_kana",
        "county_kana",
        "city_kana",
        "ward_kana",
    )
    _POSTAL_CODE_SEPARATOR: ClassVar[str] = ";"
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
            Town record for each CSV row that is not abolished.

        Raises
        ------
        FileNotFoundError
            If the file does not exist.
        RegistryFormatError
            If the archive has no CSV file, required columns are missing, a row is short,
            or a code is malformed. The message names the row.
        """
        rows = AbrCsvFile(path).read_rows()
        header = next(rows, None)
        if header is None:
            raise RegistryFormatError("Town master CSV is empty.")
        missing_columns = [
            column for column in AbrDataset.TOWN.required_columns if column not in header
        ]
        if missing_columns:
            raise RegistryFormatError(f"Town master CSV lacks required columns: {missing_columns}.")
        column_index = {column: header.index(column) for column in AbrDataset.TOWN.required_columns}
        municipalities: dict[tuple[str, ...], Municipality] = {}
        for row_number, row in enumerate(rows, start=2):
            if len(row) < len(header):
                raise RegistryFormatError(
                    f"Row {row_number} has {len(row)} columns, expected {len(header)}."
                )
            values = {column: row[index] for column, index in column_index.items()}
            if values["ablt_date"]:
                continue
            try:
                town = self._to_town(values, municipalities)
            except ValueError as error:
                raise RegistryFormatError(f"Row {row_number}: {error}") from error
            yield town

    def _to_town(
        self, values: dict[str, str], municipalities: dict[tuple[str, ...], Municipality]
    ) -> Town:
        municipality_values = tuple(values[column] for column in self._MUNICIPALITY_COLUMNS)
        if municipality_values not in municipalities:
            municipalities[municipality_values] = self._to_municipality(values)
        return Town(
            municipality=municipalities[municipality_values],
            machiaza_id=values["machiaza_id"].zfill(7),
            oaza_name=values["oaza_cho"],
            chome_name=values["chome"],
            chome_number=self._parse_chome_number(values["chome"]),
            koaza_name=values["koaza"],
            oaza_kana=values["oaza_cho_kana"],
            chome_kana=values["chome_kana"],
            koaza_kana=values["koaza_kana"],
            postal_codes=self._parse_postal_codes(values["post_code"]),
            is_registered=True,
        )

    def _to_municipality(self, values: dict[str, str]) -> Municipality:
        return Municipality(
            lg_code=values["lg_code"].zfill(6),
            prefecture_name=values["pref"],
            county_name=values["county"],
            city_name=values["city"],
            ward_name=values["ward"],
            prefecture_kana=values["pref_kana"],
            county_kana=values["county_kana"],
            city_kana=values["city_kana"],
            ward_kana=values["ward_kana"],
        )

    def _parse_postal_codes(self, text: str) -> tuple[str, ...]:
        if not text:
            return ()
        return tuple(sorted(text.split(self._POSTAL_CODE_SEPARATOR)))

    def _parse_chome_number(self, chome_name: str) -> int | None:
        matched = self._CHOME.fullmatch(chome_name)
        if matched is None:
            return None
        number = matched.group("number")
        if number[0] in KanjiNumeral.CHARACTERS:
            return KanjiNumeral.to_int(number)
        return int(number)
