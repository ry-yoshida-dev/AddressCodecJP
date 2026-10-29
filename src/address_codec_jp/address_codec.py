from pathlib import Path
from types import TracebackType
from typing import Self

from geo_coordinate import GeoCoordinate, GeodeticCrs

from address_codec_jp.domain.address_code import AddressCode
from address_codec_jp.domain.address_level import AddressLevel
from address_codec_jp.domain.address_location import AddressLocation
from address_codec_jp.domain.address_match import AddressMatch
from address_codec_jp.domain.nearest_address import NearestAddress
from address_codec_jp.formatting.address_format import AddressFormat
from address_codec_jp.formatting.address_formatter import AddressFormatter
from address_codec_jp.matching.area_matcher import AreaMatcher
from address_codec_jp.normalization.lot_number_parser import LotNumberParser
from address_codec_jp.normalization.text_normalizer import TextNormalizer
from address_codec_jp.positioning.address_locator import AddressLocator
from address_codec_jp.positioning.nearest_address_finder import NearestAddressFinder
from address_codec_jp.storage.abr_position_csv_reader import AbrPositionCsvReader
from address_codec_jp.storage.abr_town_csv_reader import AbrTownCsvReader
from address_codec_jp.storage.import_summary import ImportSummary
from address_codec_jp.storage.position_import_summary import PositionImportSummary
from address_codec_jp.storage.position_repository import PositionRepository
from address_codec_jp.storage.town_repository import TownRepository


class AddressCodec:
    """
    Converter between free-form Japanese addresses, address codes, and coordinates.

    A codec holds one SQLite connection and must be used only in the thread that opened it.

    Parameters
    ----------
    repository : TownRepository
        Town dictionary used for matching and decoding.
    position_repository : PositionRepository
        Representative points used for locating. It shares the town database.

    Examples
    --------
    >>> with AddressCodec.open("towns.sqlite3") as codec:  # doctest: +SKIP
    ...     code = codec.encode("東京都千代田区丸の内１丁目２番３号")
    ...     codec.decode(code)
    '東京都千代田区丸の内1丁目2番3号'
    """

    def __init__(self, repository: TownRepository, position_repository: PositionRepository) -> None:
        self._repository: TownRepository = repository
        self._locator: AddressLocator = AddressLocator(position_repository)
        self._nearest_finder: NearestAddressFinder = NearestAddressFinder(position_repository)
        self._position_repository: PositionRepository = position_repository
        self._normalizer: TextNormalizer = TextNormalizer()
        self._matcher: AreaMatcher = self._create_matcher()
        self._formatter: AddressFormatter = AddressFormatter()

    def _create_matcher(self) -> AreaMatcher:
        return AreaMatcher(self._repository, self._normalizer, LotNumberParser())

    @classmethod
    def open(cls, database_path: Path | str) -> Self:
        """
        Open a codec backed by an existing town database in read-only mode.

        Use ``create`` to import a town master.

        Parameters
        ----------
        database_path : Path | str
            SQLite file created by ``create`` and ``import_town_master``.

        Returns
        -------
        Self
            Codec bound to the database.

        Raises
        ------
        FileNotFoundError
            If the database file does not exist.
        ValueError
            If the file is an SQLite database without a town table.
        """
        repository = TownRepository.open(database_path)
        return cls(repository, PositionRepository(repository.connection))

    @classmethod
    def create(cls, database_path: Path | str) -> Self:
        """
        Open a codec backed by a town database, creating the file if needed.

        Use this before ``import_town_master`` and ``import_positions``.

        Parameters
        ----------
        database_path : Path | str
            SQLite file path, or ``":memory:"`` for an in-memory database.

        Returns
        -------
        Self
            Codec bound to the database.
        """
        repository = TownRepository.create(database_path)
        position_repository = PositionRepository(repository.connection)
        position_repository.create_schema()
        return cls(repository, position_repository)

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
        self._repository.close()

    def import_town_master(self, path: Path) -> ImportSummary:
        """
        Replace the database contents with the Address Base Registry town master.

        Oaza-level towns are added for oaza registered only by chome, so that
        addresses ending at the oaza, such as ``台東区浅草橋``, can be encoded.
        Towns of the previous import that are not in the new master are removed, together
        with their imported points and lot numbers. Abolished rows are skipped.

        Parameters
        ----------
        path : Path
            ``mt_town_all.csv`` or a ZIP archive containing it.

        Returns
        -------
        ImportSummary
            Numbers of registered and added towns and of removed position rows.

        Raises
        ------
        FileNotFoundError
            If the file does not exist.
        ValueError
            If the file is malformed. The previous contents are kept in that case.
        """
        replacement = self._repository.replace_all(AbrTownCsvReader().read(path))
        removed_position_count = self._position_repository.remove_orphans()
        self._matcher = self._create_matcher()
        return ImportSummary(
            registered_count=replacement.registered_count,
            complemented_count=replacement.complemented_count,
            removed_position_count=removed_position_count,
        )

    def import_positions(self, path: Path) -> PositionImportSummary:
        """
        Add one position-related dataset of the Address Base Registry to the database.

        Accepted are the position extensions of the prefecture, municipality, town,
        block, residence, and parcel masters, and the block, residence, and parcel
        masters that map lot numbers to the identifiers of the extensions. A lot is
        located only when both its master and its extension are imported, in any order.
        Rows with the same identifiers as earlier imports are replaced, and lots that a
        master marks abolished are removed.

        Parameters
        ----------
        path : Path
            Registry CSV file or its ZIP archive, e.g. ``mt_town_pos_pref13.csv.zip``.

        Returns
        -------
        PositionImportSummary
            Dataset of the file and numbers of stored rows and removed lots.

        Raises
        ------
        FileNotFoundError
            If the file does not exist.
        ValueError
            If the file is not a position-related dataset or is malformed. Nothing is
            stored in that case.
        """
        reader = AbrPositionCsvReader()
        dataset = reader.detect(path)
        changes = self._position_repository.save_all(reader.read(path))
        return PositionImportSummary(
            dataset=dataset,
            stored_count=changes.stored_count,
            removed_count=changes.removed_count,
        )

    def match(self, address: str, is_lot_verified: bool = False) -> AddressMatch:
        """
        Interpret a free-form address.

        Parameters
        ----------
        address : str
            Address in any common notation.
        is_lot_verified : bool
            Whether lot numbers must be registered in the imported block, residence, or
            parcel masters. Without verification, any lot numbers are accepted.

        Returns
        -------
        AddressMatch
            Matched prefecture, municipality, town, lot numbers, and unparsed remainder.
            The address may end at the prefecture, municipality, oaza, or chome. A
            leading postal code decides between equally good readings.

        Raises
        ------
        ValueError
            If the address is blank.
        LookupError
            If the address does not match a registered area, or is ambiguous. With
            verification, also if no lot of the town is imported or its lot numbers are
            not registered.
        RuntimeError
            If the database contains no towns, or verification is requested before any
            block, residence, or parcel master has been imported.
        """
        normalized_address = self._normalizer.normalize(address)
        if not normalized_address:
            raise ValueError("Address must not be blank.")
        postal_code = self._normalizer.extract_postal_code(address)
        area_match = self._matcher.match(normalized_address, postal_code)
        address_match = AddressMatch(
            normalized_address=normalized_address,
            prefecture=area_match.prefecture,
            municipality=area_match.municipality,
            town=area_match.town,
            lot=area_match.lot,
            remainder=area_match.remainder,
            postal_code=postal_code,
        )
        if is_lot_verified:
            self._verify_lot(address_match.code)
        return address_match

    def _verify_lot(self, code: AddressCode) -> None:
        if not self._position_repository.is_lot_imported:
            raise RuntimeError(
                "No block, residence, or parcel master has been imported to verify lot numbers."
            )
        if code.machiaza_id is None or not code.lot.numbers:
            return
        if not self._position_repository.has_lots(code.lg_code, code.machiaza_id):
            raise LookupError(f"No block, residence, or parcel of {code} has been imported.")
        if not self._position_repository.contains_lot(code.lg_code, code.machiaza_id, code.lot):
            raise LookupError(f"Lot numbers of {code} are not registered.")

    def encode(self, address: str, is_lot_verified: bool = False) -> AddressCode:
        """
        Convert an address to its address code.

        Parameters
        ----------
        address : str
            Address in any common notation.
        is_lot_verified : bool
            Whether lot numbers must be registered in the imported block, residence, or
            parcel masters.

        Returns
        -------
        AddressCode
            Code of the address at the most specific level it contains.
            Building names and room numbers are not encoded.

        Raises
        ------
        ValueError
            If the address is blank.
        LookupError
            If the address does not match a registered area, or verified lot numbers are
            not registered.
        RuntimeError
            If the database contains no towns, or verification is requested before any
            block, residence, or parcel master has been imported.
        """
        return self.match(address, is_lot_verified).code

    def decode(self, code: AddressCode | str, address_format: AddressFormat | None = None) -> str:
        """
        Convert an address code to address text.

        Parameters
        ----------
        code : AddressCode | str
            Address code or its string form.
        address_format : AddressFormat | None
            Output format. The default format is used when omitted.

        Returns
        -------
        str
            Formatted address.

        Raises
        ------
        ValueError
            If a string code is malformed, or lot numbers are attached to an oaza that
            takes them only under a chome.
        KeyError
            If the area of the code is not registered.
        LookupError
            If katakana is requested and the registry has no reading of a name.
        """
        address_code = code if isinstance(code, AddressCode) else AddressCode.parse(code)
        selected_format = address_format or AddressFormat()
        match address_code.level:
            case AddressLevel.PREFECTURE:
                return self._formatter.format_prefecture(
                    self._repository.get_prefecture(address_code.prefecture_code), selected_format
                )
            case AddressLevel.MUNICIPALITY:
                return self._formatter.format_municipality(
                    self._repository.get_municipality(address_code.lg_code), selected_format
                )
            case AddressLevel.TOWN:
                if address_code.machiaza_id is None:
                    raise RuntimeError("A town-level code must have a machiaza_id.")
                town = self._repository.get_town(address_code.lg_code, address_code.machiaza_id)
                if not town.is_registered and address_code.lot.numbers:
                    raise ValueError(
                        f"{address_code} has lot numbers, but {town.oaza_name} takes lot "
                        + "numbers only under a chome."
                    )
                return self._formatter.format_town(town, address_code.lot, selected_format)

    def locate(self, address: str, crs: GeodeticCrs = GeodeticCrs.JGD2011) -> AddressLocation:
        """
        Find the representative point of a free-form address.

        Parameters
        ----------
        address : str
            Address in any common notation.
        crs : GeodeticCrs
            Datum of the returned coordinate.

        Returns
        -------
        AddressLocation
            Point of the address, or of its nearest enclosing area when the registry has
            no point for the address itself.

        Raises
        ------
        ValueError
            If the address is blank.
        LookupError
            If the address does not match a registered area, or neither the address nor
            any enclosing area has an imported point.
        RuntimeError
            If no town or no position has been imported, or the published datum cannot
            be transformed to ``crs``.
        """
        return self._locator.locate(self.encode(address), crs)

    def locate_code(
        self, code: AddressCode | str, crs: GeodeticCrs = GeodeticCrs.JGD2011
    ) -> AddressLocation:
        """
        Find the representative point of an address code.

        Parameters
        ----------
        code : AddressCode | str
            Address code or its string form.
        crs : GeodeticCrs
            Datum of the returned coordinate.

        Returns
        -------
        AddressLocation
            Point of the code, or of its nearest enclosing area when the registry has no
            point for the code itself.

        Raises
        ------
        ValueError
            If a string code is malformed.
        LookupError
            If neither the code nor any enclosing area has an imported point.
        RuntimeError
            If no position has been imported, or the published datum cannot be
            transformed to ``crs``.
        """
        address_code = code if isinstance(code, AddressCode) else AddressCode.parse(code)
        return self._locator.locate(address_code, crs)

    def find_nearest(
        self,
        coordinate: GeoCoordinate,
        crs: GeodeticCrs = GeodeticCrs.JGD2011,
        max_distance_meters: float = 1000.0,
    ) -> NearestAddress:
        """
        Find the address whose representative point is nearest to a coordinate.

        Blocks, residences, and parcels are preferred; the nearest town is returned only
        when no lot point is within ``max_distance_meters``.

        Parameters
        ----------
        coordinate : GeoCoordinate
            Searched coordinate on ``crs``.
        crs : GeodeticCrs
            Datum of ``coordinate`` and of the returned point.
        max_distance_meters : float
            Largest accepted distance to a representative point.

        Returns
        -------
        NearestAddress
            Code, point, and distance of the nearest address.

        Raises
        ------
        ValueError
            If ``max_distance_meters`` is not positive.
        LookupError
            If no imported point is within ``max_distance_meters``.
        RuntimeError
            If no position has been imported, or ``crs`` cannot be transformed.
        """
        return self._nearest_finder.find(coordinate, crs, max_distance_meters)
