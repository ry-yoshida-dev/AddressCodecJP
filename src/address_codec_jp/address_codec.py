from pathlib import Path
from types import TracebackType
from typing import ClassVar, Self

from geo_coordinate import GeoCoordinate, GeodeticCrs

from address_codec_jp.database_cache import DatabaseCache
from address_codec_jp.domain.address import Address
from address_codec_jp.domain.address_code import AddressCode
from address_codec_jp.domain.address_level import AddressLevel
from address_codec_jp.domain.address_location import AddressLocation
from address_codec_jp.domain.address_match import AddressMatch
from address_codec_jp.domain.nearest_address import NearestAddress
from address_codec_jp.errors.address_not_found_error import AddressNotFoundError
from address_codec_jp.errors.dataset_not_imported_error import DatasetNotImportedError
from address_codec_jp.formatting.address_format import AddressFormat
from address_codec_jp.formatting.address_formatter import AddressFormatter
from address_codec_jp.matching.area_matcher import AreaMatcher
from address_codec_jp.normalization.lot_number_parser import LotNumberParser
from address_codec_jp.normalization.text_normalizer import TextNormalizer
from address_codec_jp.positioning.address_locator import AddressLocator
from address_codec_jp.positioning.nearest_address_finder import NearestAddressFinder
from address_codec_jp.storage.address_database import AddressDatabase
from address_codec_jp.storage.dataset_import import DatasetImport


class AddressCodec:
    """
    Converter between free-form Japanese addresses, address codes, and coordinates.

    A codec only reads its database; use ``RegistryImporter`` to import registry
    datasets. Matching indexes are built from the database on first use, so create the
    codec after importing. A codec must be used only in the thread that opened it.

    Parameters
    ----------
    database : AddressDatabase
        Database with an imported town master. It is closed by ``close``.
    lot_cache : DatabaseCache | None
        Cache that holds ``database`` and adds blocks, residences, and land parcels of an
        area before they are needed, or ``None`` to use only what has been imported.

    Examples
    --------
    >>> with AddressCodec.open() as codec:  # doctest: +SKIP
    ...     code = codec.encode("東京都千代田区丸の内１丁目２番３号")
    ...     codec.decode(code)
    '東京都千代田区丸の内1丁目2番3号'
    """

    DEFAULT_FORMAT: ClassVar[AddressFormat] = AddressFormat()

    NEARBY_LOT_MARGIN_METERS: ClassVar[float] = 5000.0

    def __init__(self, database: AddressDatabase, lot_cache: DatabaseCache | None = None) -> None:
        self._database: AddressDatabase = database
        self._lot_cache: DatabaseCache | None = lot_cache
        self._normalizer: TextNormalizer = TextNormalizer()
        self._matcher: AreaMatcher = AreaMatcher(
            database.towns, self._normalizer, LotNumberParser()
        )
        self._formatter: AddressFormatter = AddressFormatter()
        self._locator: AddressLocator = AddressLocator(database.positions)
        self._nearest_finder: NearestAddressFinder = NearestAddressFinder(database.positions)

    @classmethod
    def open(cls, database_path: Path | str | None = None) -> Self:
        """
        Open a codec on a database in read-only mode.

        Parameters
        ----------
        database_path : Path | str | None
            SQLite file created by ``RegistryImporter``, or ``None`` for the database of
            ``DatabaseCache.default``, which is downloaded and built on first use and
            extended with the blocks, residences, and land parcels of each area that is
            located or verified.

        Returns
        -------
        Self
            Codec bound to the database.

        Raises
        ------
        FileNotFoundError
            If the database file does not exist.
        UnsupportedDatabaseError
            If the file is not a database of this version of the library.
        RegistryDownloadError
            If the default database has to be built and a registry file cannot be
            downloaded.
        """
        if database_path is not None:
            return cls(AddressDatabase.open_read_only(database_path))
        cache = DatabaseCache.default()
        return cls(AddressDatabase.open_read_only(cache.ensure()), cache)

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

    def list_imports(self) -> list[DatasetImport]:
        """
        List the registry files imported into the database.

        Returns
        -------
        list[DatasetImport]
            Imports from the oldest to the newest, with file names and SHA-256 digests
            that identify the registry release.
        """
        return self._database.imports.list_all()

    def match(self, address: str, *, is_lot_verified: bool = False) -> AddressMatch:
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
            Matched address, unparsed remainder, and how loosely names were compared.
            The address may end at the prefecture, municipality, oaza, or chome. A
            leading postal code decides between equally good readings.

        Raises
        ------
        ValueError
            If the address is blank.
        AddressNotFoundError
            If the address does not match a registered area. With verification, also if
            no lot of the town is imported or its lot numbers are not registered.
        AmbiguousAddressError
            If the address fits several areas or lot numbers equally well.
        DatasetNotImportedError
            If the database contains no towns, or verification is requested before any
            block, residence, or parcel master has been imported.
        RegistryDownloadError
            If the lots of the area have to be added to ``lot_cache`` and a registry file
            cannot be downloaded.
        """
        normalized_address = self._normalizer.normalize(address)
        if not normalized_address:
            raise ValueError("Address must not be blank.")
        address_match = self._matcher.match(
            normalized_address, self._normalizer.extract_postal_code(address)
        )
        if is_lot_verified:
            self._verify_lot(address_match.code)
        return address_match

    def _verify_lot(self, code: AddressCode) -> None:
        self._ensure_lots(code)
        positions = self._database.positions
        if not positions.is_lot_imported:
            raise DatasetNotImportedError(
                "No block, residence, or parcel master has been imported to verify lot numbers."
            )
        if code.machiaza_id is None or not code.lot.numbers:
            return
        if not positions.has_lots(code.lg_code, code.machiaza_id):
            raise AddressNotFoundError(
                f"No block, residence, or parcel of {code} has been imported."
            )
        if not positions.contains_lot(code.lg_code, code.machiaza_id, code.lot):
            raise AddressNotFoundError(f"Lot numbers of {code} are not registered.")

    def encode(self, address: str, *, is_lot_verified: bool = False) -> AddressCode:
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
        AddressNotFoundError
            If the address does not match a registered area, or verified lot numbers are
            not registered.
        AmbiguousAddressError
            If the address fits several areas or lot numbers equally well.
        DatasetNotImportedError
            If the database contains no towns, or verification is requested before any
            block, residence, or parcel master has been imported.
        RegistryDownloadError
            If the lots of the area have to be added to ``lot_cache`` and a registry file
            cannot be downloaded.
        """
        return self.match(address, is_lot_verified=is_lot_verified).code

    def resolve(self, code: AddressCode | str) -> Address:
        """
        Look up the registered areas of an address code.

        Parameters
        ----------
        code : AddressCode | str
            Address code or its string form.

        Returns
        -------
        Address
            Prefecture, municipality, town, and lot numbers of the code.

        Raises
        ------
        ValueError
            If a string code is malformed, or lot numbers are attached to an oaza that
            takes them only under a chome.
        AddressNotFoundError
            If the area of the code is not registered.
        """
        address_code = code if isinstance(code, AddressCode) else AddressCode.parse(code)
        towns = self._database.towns
        if address_code.machiaza_id is not None:
            return Address.for_town(
                towns.get_town(address_code.lg_code, address_code.machiaza_id), address_code.lot
            )
        if address_code.level is AddressLevel.PREFECTURE:
            return Address(prefecture=towns.get_prefecture(address_code.prefecture_code))
        municipality = towns.get_municipality(address_code.lg_code)
        return Address(prefecture=municipality.prefecture, municipality=municipality)

    def decode(
        self, code: AddressCode | str, address_format: AddressFormat = DEFAULT_FORMAT
    ) -> str:
        """
        Convert an address code to address text.

        Parameters
        ----------
        code : AddressCode | str
            Address code or its string form.
        address_format : AddressFormat
            Output format.

        Returns
        -------
        str
            Formatted address.

        Raises
        ------
        ValueError
            If a string code is malformed, or lot numbers are attached to an oaza that
            takes them only under a chome.
        AddressNotFoundError
            If the area of the code is not registered.
        ReadingNotFoundError
            If katakana is requested and the registry has no reading of a name.
        """
        return self._formatter.format(self.resolve(code), address_format)

    def list_by_postal_code(self, postal_code: str) -> list[Address]:
        """
        List the towns registered with a postal code.

        Parameters
        ----------
        postal_code : str
            Postal code such as ``100-0005``, ``〒1000005``, or with full-width digits.

        Returns
        -------
        list[Address]
            Town-level addresses ordered by code. Empty when no town has the postal code;
            the registry gives postal codes for only about 13% of the towns.

        Raises
        ------
        ValueError
            If the text is not a postal code.
        """
        towns = self._database.towns.list_towns_by_postal_code(
            self._normalizer.parse_postal_code(postal_code)
        )
        return [Address.for_town(town) for town in towns]

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
        AddressNotFoundError
            If the address does not match a registered area.
        AmbiguousAddressError
            If the address fits several areas or lot numbers equally well.
        PositionNotFoundError
            If neither the address nor any enclosing area has an imported point.
        DatasetNotImportedError
            If no town or no position has been imported.
        RuntimeError
            If the published datum cannot be transformed to ``crs``.
        RegistryDownloadError
            If the lots of the area have to be added to ``lot_cache`` and a registry file
            cannot be downloaded.
        """
        return self.locate_code(self.encode(address), crs)

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
        PositionNotFoundError
            If neither the code nor any enclosing area has an imported point.
        DatasetNotImportedError
            If no position has been imported.
        RuntimeError
            If the published datum cannot be transformed to ``crs``.
        RegistryDownloadError
            If the lots of the area have to be added to ``lot_cache`` and a registry file
            cannot be downloaded.
        """
        address_code = code if isinstance(code, AddressCode) else AddressCode.parse(code)
        self._ensure_lots(address_code)
        return self._locator.locate(address_code, crs)

    def _ensure_lots(self, code: AddressCode) -> None:
        if self._lot_cache is not None and code.machiaza_id is not None and code.lot.numbers:
            self._lot_cache.ensure_lots([code.lg_code])

    def find_nearest(
        self,
        coordinate: GeoCoordinate,
        crs: GeodeticCrs = GeodeticCrs.JGD2011,
        max_distance_meters: float = 1000.0,
    ) -> NearestAddress:
        """
        Find the address whose representative point is nearest to a coordinate.

        Blocks, residences, and parcels are preferred; the nearest town is returned only
        when no lot point is within ``max_distance_meters``. With a ``lot_cache``, the lots
        of the municipalities whose town points lie within ``max_distance_meters`` plus
        ``NEARBY_LOT_MARGIN_METERS`` are added first.

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
        PositionNotFoundError
            If no imported point is within ``max_distance_meters``.
        DatasetNotImportedError
            If no position has been imported.
        RuntimeError
            If ``crs`` cannot be transformed.
        RegistryDownloadError
            If the lots of the area have to be added to ``lot_cache`` and a registry file
            cannot be downloaded.
        """
        if self._lot_cache is not None and max_distance_meters > 0:
            self._lot_cache.ensure_lots(
                self._nearest_finder.list_nearby_municipalities(
                    coordinate, crs, max_distance_meters + self.NEARBY_LOT_MARGIN_METERS
                )
            )
        return self._nearest_finder.find(coordinate, crs, max_distance_meters)
