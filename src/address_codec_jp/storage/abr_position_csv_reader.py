from collections.abc import Iterator
from pathlib import Path

from geo_coordinate import GeodeticCrs

from address_codec_jp.domain.lot_number import LotNumber
from address_codec_jp.domain.lot_system import LotSystem
from address_codec_jp.domain.representative_point import RepresentativePoint
from address_codec_jp.domain.town_position import TownPosition
from address_codec_jp.errors.registry_format_error import RegistryFormatError
from address_codec_jp.storage.abr_csv_file import AbrCsvFile
from address_codec_jp.storage.abr_position_dataset import AbrPositionDataset
from address_codec_jp.storage.area_position import AreaPosition
from address_codec_jp.storage.lot_entry import LotEntry
from address_codec_jp.storage.lot_position import LotPosition
from address_codec_jp.storage.lot_removal import LotRemoval
from address_codec_jp.storage.position_record import PositionRecord


class AbrPositionCsvReader:
    """
    Reader for the position-related CSV files of the Address Base Registry.

    The dataset is identified by the header, so the files may be renamed. Both plain
    ``.csv`` files and ``.zip`` archives are accepted. Abolished rows of the block,
    residence, and parcel masters become ``LotRemoval`` records. Rows that address codes
    cannot express are skipped: rows without a point, residences with a second residence
    number, parcels with a third number, and non-numeric lot numbers.
    """

    def detect(self, path: Path) -> AbrPositionDataset:
        """
        Identify the dataset of a file.

        Parameters
        ----------
        path : Path
            Registry file.

        Returns
        -------
        AbrPositionDataset
            Dataset of the file.

        Raises
        ------
        FileNotFoundError
            If the file does not exist.
        RegistryFormatError
            If the file is empty or not a position-related dataset.
        """
        return AbrPositionDataset.detect(self._read_header(AbrCsvFile(path).read_rows()))

    def read(self, path: Path) -> Iterator[PositionRecord]:
        """
        Read the records of a file.

        Parameters
        ----------
        path : Path
            Registry file.

        Yields
        ------
        PositionRecord
            Record for each row that address codes can express, and a removal for each
            abolished lot.

        Raises
        ------
        FileNotFoundError
            If the file does not exist.
        RegistryFormatError
            If the file is not a position-related dataset, required columns are
            missing, a row is short, or a value is malformed. The message names the row.
        """
        rows = AbrCsvFile(path).read_rows()
        header = self._read_header(rows)
        dataset = AbrPositionDataset.detect(header)
        missing_columns = [column for column in dataset.required_columns if column not in header]
        if missing_columns:
            raise RegistryFormatError(
                f"{dataset.value} CSV lacks required columns: {missing_columns}."
            )
        column_index = {column: header.index(column) for column in dataset.required_columns}
        for row_number, row in enumerate(rows, start=2):
            if len(row) < len(header):
                raise RegistryFormatError(
                    f"Row {row_number} has {len(row)} columns, expected {len(header)}."
                )
            values = {column: row[index] for column, index in column_index.items()}
            try:
                record = self._to_record(dataset, values)
            except ValueError as error:
                raise RegistryFormatError(f"Row {row_number}: {error}") from error
            if record is not None:
                yield record

    def _read_header(self, rows: Iterator[list[str]]) -> list[str]:
        header = next(rows, None)
        if header is None:
            raise RegistryFormatError("Registry CSV is empty.")
        return header

    def _to_record(
        self, dataset: AbrPositionDataset, values: dict[str, str]
    ) -> PositionRecord | None:
        lg_code = values["lg_code"].zfill(6)
        match dataset:
            case AbrPositionDataset.AREA_POSITION:
                point = self._to_point(values)
                return None if point is None else AreaPosition(lg_code=lg_code, point=point)
            case AbrPositionDataset.TOWN_POSITION:
                point = self._to_point(values)
                if point is None:
                    return None
                return TownPosition(
                    lg_code=lg_code,
                    machiaza_id=values["machiaza_id"].zfill(7),
                    lot_system=self._to_lot_system(values["rsdt_addr_flg"]),
                    point=point,
                )
            case AbrPositionDataset.BLOCK:
                return self._to_entry(
                    values, LotSystem.RESIDENCE_INDICATION, values["blk_id"], [values["blk_num"]]
                )
            case AbrPositionDataset.RESIDENCE:
                if values["rsdt_num2"] and not values["ablt_date"]:
                    return None
                return self._to_entry(
                    values,
                    LotSystem.RESIDENCE_INDICATION,
                    self._residence_id(values),
                    [values["blk_num"], values["rsdt_num"]],
                )
            case AbrPositionDataset.PARCEL:
                if values["prc_num3"] and not values["ablt_date"]:
                    return None
                return self._to_entry(
                    values,
                    LotSystem.LAND_PARCEL,
                    values["prc_id"],
                    [number for number in (values["prc_num1"], values["prc_num2"]) if number],
                )
            case AbrPositionDataset.BLOCK_POSITION:
                return self._to_lot_position(
                    values, LotSystem.RESIDENCE_INDICATION, values["blk_id"]
                )
            case AbrPositionDataset.RESIDENCE_POSITION:
                return self._to_lot_position(
                    values, LotSystem.RESIDENCE_INDICATION, self._residence_id(values)
                )
            case AbrPositionDataset.PARCEL_POSITION:
                return self._to_lot_position(values, LotSystem.LAND_PARCEL, values["prc_id"])

    def _to_entry(
        self, values: dict[str, str], lot_system: LotSystem, lot_id: str, numbers: list[str]
    ) -> LotEntry | LotRemoval | None:
        if values["ablt_date"]:
            return LotRemoval(
                lg_code=values["lg_code"].zfill(6),
                machiaza_id=values["machiaza_id"].zfill(7),
                lot_system=lot_system,
                lot_id=lot_id,
            )
        if not all(number.isascii() and number.isdecimal() for number in numbers):
            return None
        parsed_numbers = [int(number) for number in numbers]
        if 0 in parsed_numbers:
            return None
        return LotEntry(
            lg_code=values["lg_code"].zfill(6),
            machiaza_id=values["machiaza_id"].zfill(7),
            lot_system=lot_system,
            lot_id=lot_id,
            lot=LotNumber(
                block=parsed_numbers[0],
                residence=parsed_numbers[1] if len(parsed_numbers) > 1 else None,
            ),
        )

    def _to_lot_position(
        self, values: dict[str, str], lot_system: LotSystem, lot_id: str
    ) -> LotPosition | None:
        point = self._to_point(values)
        if point is None:
            return None
        return LotPosition(
            lg_code=values["lg_code"].zfill(6),
            machiaza_id=values["machiaza_id"].zfill(7),
            lot_system=lot_system,
            lot_id=lot_id,
            point=point,
        )

    def _residence_id(self, values: dict[str, str]) -> str:
        return "-".join((values["blk_id"], values["rsdt_id"], values["rsdt2_id"]))

    def _to_point(self, values: dict[str, str]) -> RepresentativePoint | None:
        if not values["rep_lon"] or not values["rep_lat"]:
            return None
        srid = values["rep_srid"]
        if not srid.startswith("EPSG:"):
            raise ValueError(f"Unsupported spatial reference {srid!r}.")
        return RepresentativePoint(
            longitude=float(values["rep_lon"]),
            latitude=float(values["rep_lat"]),
            crs=GeodeticCrs(int(srid.removeprefix("EPSG:"))),
        )

    def _to_lot_system(self, residence_indication_flag: str) -> LotSystem:
        match residence_indication_flag:
            case "1":
                return LotSystem.RESIDENCE_INDICATION
            case "0":
                return LotSystem.LAND_PARCEL
            case _:
                raise ValueError(
                    f"rsdt_addr_flg must be 0 or 1, got {residence_indication_flag!r}."
                )
