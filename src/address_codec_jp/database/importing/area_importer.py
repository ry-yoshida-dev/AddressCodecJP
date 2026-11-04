import hashlib
import re
import zipfile
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import ClassVar, Self

from address_codec_jp.address import AddressCode, LotNumber
from address_codec_jp.database.importing.census_area_matcher import CensusAreaMatcher
from address_codec_jp.database.storage import (
    AddressDatabase,
    AreaBatch,
    AreaImport,
    AreaRecord,
    CensusAreaRecord,
)
from address_codec_jp.datasets.boundaries import CensusBoundaryReader, RegistryMapReader
from address_codec_jp.errors import BoundaryFormatError
from address_codec_jp.results import AddressMatch, AreaSource
from address_codec_jp.text.matching import AreaMatcher
from address_codec_jp.text.normalization import LotNumberParser, TextNormalizer


class AreaImporter:
    """
    Importer of area shapes into an address database with an imported town master.

    Shapes carry names, not registry codes, so each is matched to a registered town by
    its address text, census areas through ``CensusAreaMatcher``. Every census area is
    stored under its census code, those that fit no town or several equally well without
    one and counted, so that a municipality is whole however its names were matched. A
    land parcel is stored under the code of its town and its parcel number; parcels that
    fit no town are skipped and counted.

    Parameters
    ----------
    database : AddressDatabase
        Writable database with an imported town master. It is closed by ``close``.

    Raises
    ------
    ValueError
        If the database was opened read-only.
    """

    _HASH_CHUNK_SIZE: ClassVar[int] = 1 << 20
    _LOT_PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"(\d+)(?:-(\d+))?")

    def __init__(self, database: AddressDatabase) -> None:
        if not database.is_writable:
            raise ValueError("AreaImporter requires a database opened for writing.")
        self._database: AddressDatabase = database
        self._normalizer: TextNormalizer = TextNormalizer()
        self._matcher: AreaMatcher = AreaMatcher(
            database.towns, self._normalizer, LotNumberParser()
        )
        self._census_matcher: CensusAreaMatcher = CensusAreaMatcher(
            database.towns, self._normalizer, self._matcher
        )

    @classmethod
    def open(cls, database_path: Path | str) -> Self:
        """
        Open an importer on an existing database.

        Parameters
        ----------
        database_path : Path | str
            SQLite file with an imported town master.

        Returns
        -------
        Self
            Importer bound to the database.

        Raises
        ------
        UnsupportedDatabaseError
            If the file is not a database of this version of the library.
        """
        return cls(AddressDatabase.open_writable(database_path))

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying database."""
        self._database.close()

    def import_file(self, path: Path, lg_code: str) -> AreaImport:
        """
        Import a census boundary archive or a registry map archive.

        Parameters
        ----------
        path : Path
            ZIP archive of a census boundary shapefile, or of registry map sheets, or one
            map XML file.
        lg_code : str
            Six-digit local government code of the municipality or prefecture the file
            covers, recorded in the import log.

        Returns
        -------
        AreaImport
            Logged import with the numbers of stored and skipped shapes.

        Raises
        ------
        ValueError
            If ``lg_code`` is malformed.
        BoundaryFormatError
            If the file is neither kind of archive or is malformed.
        DatasetNotImportedError
            If the database contains no towns.
        """
        return self.import_files([path], lg_code)[0]

    def import_files(self, paths: Sequence[Path], lg_code: str) -> list[AreaImport]:
        """
        Import the area files of one municipality in one transaction.

        A municipality can have several registry map archives, one per registry office.
        They are stored together or not at all, so that a failure never leaves the
        municipality logged as imported with only some of its maps.

        Parameters
        ----------
        paths : Sequence[Path]
            Files accepted by ``import_file``.
        lg_code : str
            Six-digit local government code of the municipality or prefecture the files
            cover, recorded in the import log.

        Returns
        -------
        list[AreaImport]
            Logged imports in the order of ``paths``.

        Raises
        ------
        ValueError
            If ``lg_code`` is malformed.
        BoundaryFormatError
            If a file is neither kind of archive or is malformed; nothing is stored then.
        DatasetNotImportedError
            If the database contains no towns.
        """
        area_code = AddressCode(lg_code=lg_code)
        with self._database.transaction():
            return [self._import(path, area_code) for path in paths]

    @staticmethod
    def detect(path: Path) -> AreaSource:
        """
        Identify the dataset of an area file by its contents.

        Parameters
        ----------
        path : Path
            Candidate file.

        Returns
        -------
        AreaSource
            ``CENSUS_BOUNDARY`` for an archive with a shapefile, ``REGISTRY_MAP`` for a
            map XML file or an archive of them.

        Raises
        ------
        BoundaryFormatError
            If the file is neither.
        """
        if path.suffix.lower() == ".xml":
            return AreaSource.REGISTRY_MAP
        if not zipfile.is_zipfile(path):
            raise BoundaryFormatError(f"{path} is neither a ZIP archive nor a map XML file.")
        try:
            with zipfile.ZipFile(path) as archive:
                suffixes = {Path(name).suffix.lower() for name in archive.namelist()}
        except zipfile.BadZipFile as error:
            raise BoundaryFormatError(f"{path} is not a valid ZIP archive: {error}") from error
        if ".shp" in suffixes:
            return AreaSource.CENSUS_BOUNDARY
        if suffixes & {".xml", ".zip"}:
            return AreaSource.REGISTRY_MAP
        raise BoundaryFormatError(f"{path} holds neither a shapefile nor map XML files.")

    def _import(self, path: Path, area_code: AddressCode) -> AreaImport:
        source = self.detect(path)
        match source:
            case AreaSource.CENSUS_BOUNDARY:
                census_areas = self._read_census_boundary(path, area_code.lg_code)
                stored_count = self._database.areas.save_census_areas(census_areas)
                unmatched_count = sum(
                    1 for area in census_areas if area.is_land and area.name and not area.towns
                )
            case AreaSource.REGISTRY_MAP:
                batch = self._read_registry_map(path, area_code)
                stored_count = self._database.areas.save_parcels(batch.records)
                unmatched_count = batch.unmatched_count
        area_import = AreaImport(
            source=source,
            lg_code=area_code.lg_code,
            source_name=path.name,
            source_sha256=self._digest(path),
            imported_at=datetime.now(UTC),
            stored_count=stored_count,
            unmatched_count=unmatched_count,
        )
        self._database.areas.add_import(area_import)
        return area_import

    def _read_census_boundary(self, path: Path, lg_code: str) -> list[CensusAreaRecord]:
        records: list[CensusAreaRecord] = []
        for area in CensusBoundaryReader().read(path):
            area_lg_code = AddressCode.with_check_digit(area.key_code[:5])
            is_matched = area.is_land and bool(area.town_name)
            code = self._census_matcher.match(area, lg_code) if is_matched else None
            records.append(
                CensusAreaRecord(
                    key_code=area.key_code,
                    lg_code=area_lg_code,
                    name=area.town_name,
                    shape=area.shape,
                    is_land=area.is_land,
                    towns=(
                        frozenset({code})
                        if code is not None and code.lg_code == area_lg_code
                        else frozenset()
                    ),
                )
            )
        return records

    def _read_registry_map(self, path: Path, area_code: AddressCode) -> AreaBatch:
        municipality = self._database.towns.get_municipality(area_code.lg_code)
        municipality_text = (
            municipality.prefecture_name
            + municipality.county_name
            + municipality.city_name
            + municipality.ward_name
        )
        towns: dict[tuple[str, str], AddressCode | None] = {}
        records: dict[AddressCode, AreaRecord] = {}
        unmatched_count = 0
        for parcel in RegistryMapReader().read(path):
            town_key = (parcel.oaza_name, parcel.chome_name)
            if town_key not in towns:
                towns[town_key] = self._match_town(
                    municipality_text + parcel.oaza_name + parcel.chome_name, area_code.lg_code
                )
            town = towns[town_key]
            lot = self._parse_lot(parcel.lot_text)
            if town is None or town.machiaza_id is None or lot is None:
                unmatched_count += 1
                continue
            code = AddressCode(lg_code=town.lg_code, machiaza_id=town.machiaza_id, lot=lot)
            records[code] = AreaRecord(
                code=code, source=AreaSource.REGISTRY_MAP, shape=parcel.shape
            )
        return AreaBatch(records=list(records.values()), unmatched_count=unmatched_count)

    def _match_town(self, address: str, lg_code: str) -> AddressCode | None:
        matched = self._match(address)
        if matched is None:
            return None
        code = matched.code
        is_town = code.machiaza_id is not None and not code.lot.numbers and not matched.remainder
        return code if is_town and code.lg_code == lg_code else None

    def _match(self, address: str) -> AddressMatch | None:
        return self._matcher.find(self._normalizer.normalize(address), None)

    def _parse_lot(self, lot_text: str) -> LotNumber | None:
        match_result = self._LOT_PATTERN.fullmatch(self._normalizer.normalize(lot_text))
        if match_result is None:
            return None
        residence = match_result.group(2)
        return LotNumber(
            block=int(match_result.group(1)),
            residence=None if residence is None else int(residence),
        )

    def _digest(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            while chunk := stream.read(self._HASH_CHUNK_SIZE):
                digest.update(chunk)
        return digest.hexdigest()
