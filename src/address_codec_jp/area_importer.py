import hashlib
import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import ClassVar, Self

from address_codec_jp.boundary.census_boundary_reader import CensusBoundaryReader
from address_codec_jp.boundary.registry_map_reader import RegistryMapReader
from address_codec_jp.domain.address_code import AddressCode
from address_codec_jp.domain.address_match import AddressMatch
from address_codec_jp.domain.area_shape import AreaShape
from address_codec_jp.domain.area_source import AreaSource
from address_codec_jp.domain.lot_number import LotNumber
from address_codec_jp.errors.boundary_format_error import BoundaryFormatError
from address_codec_jp.matching.area_matcher import AreaMatcher
from address_codec_jp.normalization.lot_number_parser import LotNumberParser
from address_codec_jp.normalization.text_normalizer import TextNormalizer
from address_codec_jp.storage.address_database import AddressDatabase
from address_codec_jp.storage.area_batch import AreaBatch
from address_codec_jp.storage.area_import import AreaImport
from address_codec_jp.storage.area_record import AreaRecord


class AreaImporter:
    """
    Importer of area shapes into an address database with an imported town master.

    Shapes carry names, not registry codes, so each is matched to a registered town by
    its address text. A census area whose name continues past a registered oaza, such
    as a group of koaza, becomes part of the shape of that oaza; areas that fit no town
    or several equally well are skipped and counted. A land parcel is stored under the
    code of its town and its parcel number.

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
    _MINIMUM_KOAZA_LENGTH: ClassVar[int] = 2
    _SEPARATORS: ClassVar[str] = ",、，・"

    def __init__(self, database: AddressDatabase) -> None:
        if not database.is_writable:
            raise ValueError("AreaImporter requires a database opened for writing.")
        self._database: AddressDatabase = database
        self._normalizer: TextNormalizer = TextNormalizer()
        self._matcher: AreaMatcher = AreaMatcher(
            database.towns, self._normalizer, LotNumberParser()
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
        area_code = AddressCode(lg_code=lg_code)
        source = self.detect(path)
        match source:
            case AreaSource.CENSUS_BOUNDARY:
                batch = self._read_census_boundary(path)
            case AreaSource.REGISTRY_MAP:
                batch = self._read_registry_map(path, area_code)
        digest = self._digest(path)
        with self._database.transaction():
            stored_count = self._database.areas.save_all(batch.records)
            area_import = AreaImport(
                source=source,
                lg_code=area_code.lg_code,
                source_name=path.name,
                source_sha256=digest,
                imported_at=datetime.now(UTC),
                stored_count=stored_count,
                unmatched_count=batch.unmatched_count,
            )
            self._database.areas.add_import(area_import)
        return area_import

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
        with zipfile.ZipFile(path) as archive:
            suffixes = {Path(name).suffix.lower() for name in archive.namelist()}
        if ".shp" in suffixes:
            return AreaSource.CENSUS_BOUNDARY
        if suffixes & {".xml", ".zip"}:
            return AreaSource.REGISTRY_MAP
        raise BoundaryFormatError(f"{path} holds neither a shapefile nor map XML files.")

    def _read_census_boundary(self, path: Path) -> AreaBatch:
        shapes: dict[AddressCode, AreaShape] = {}
        unmatched_count = 0
        for area in CensusBoundaryReader().read(path):
            code = self._match_census_area(area.address)
            if code is None:
                unmatched_count += 1
                continue
            existing = shapes.get(code)
            shapes[code] = area.shape if existing is None else existing.merge(area.shape)
        records = [
            AreaRecord(code=code, source=AreaSource.CENSUS_BOUNDARY, shape=shape)
            for code, shape in shapes.items()
        ]
        return AreaBatch(records=records, unmatched_count=unmatched_count)

    def _match_census_area(self, address: str) -> AddressCode | None:
        matched = self._match(address)
        if matched is None:
            return None
        code = matched.code
        remainder = matched.remainder
        if code.machiaza_id is None or code.lot.numbers:
            return None
        if not remainder:
            return code
        is_koaza_of_oaza = (
            code.machiaza_id.endswith("000")
            and len(remainder) >= self._MINIMUM_KOAZA_LENGTH
            and remainder[0] not in self._SEPARATORS
        )
        return code if is_koaza_of_oaza else None

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
