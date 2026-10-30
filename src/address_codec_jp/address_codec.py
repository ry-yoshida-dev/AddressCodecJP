from pathlib import Path
from types import TracebackType
from typing import ClassVar, Self

from geo_coordinate import GeoCoordinate, GeodeticCrs

from address_codec_jp.address import Address, AddressCode, AddressLevel
from address_codec_jp.database.cache import DatabaseCache
from address_codec_jp.database.storage import AddressDatabase, AreaImport, DatasetImport
from address_codec_jp.errors import AddressNotFoundError, DatasetNotImportedError
from address_codec_jp.geocoding import AddressLocator, AreaFinder, NearestAddressFinder
from address_codec_jp.results import AddressArea, AddressLocation, AddressMatch, NearestAddress
from address_codec_jp.text.formatting import AddressFormat, AddressFormatter
from address_codec_jp.text.matching import AreaMatcher
from address_codec_jp.text.normalization import LotNumberParser, TextNormalizer


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
    cache : DatabaseCache | None
        Cache that holds ``database`` and adds the points and shapes of a municipality
        before they are needed, or ``None`` to use only what has been imported.

    Examples
    --------
    >>> with AddressCodec.open() as codec:  # doctest: +SKIP
    ...     code = codec.encode("東京都千代田区丸の内１丁目２番３号")
    ...     codec.decode(code)
    '東京都千代田区丸の内1丁目2番3号'
    """

    DEFAULT_FORMAT: ClassVar[AddressFormat] = AddressFormat()

    NEARBY_LOT_MARGIN_METERS: ClassVar[float] = 5000.0
    NEARBY_AREA_RADII_METERS: ClassVar[tuple[float, ...]] = (1000.0, 5000.0)

    def __init__(self, database: AddressDatabase, cache: DatabaseCache | None = None) -> None:
        self._database: AddressDatabase = database
        self._cache: DatabaseCache | None = cache
        self._normalizer: TextNormalizer = TextNormalizer()
        self._matcher: AreaMatcher = AreaMatcher(
            database.towns, self._normalizer, LotNumberParser()
        )
        self._formatter: AddressFormatter = AddressFormatter()
        self._locator: AddressLocator = AddressLocator(database.positions)
        self._nearest_finder: NearestAddressFinder = NearestAddressFinder(database.positions)
        self._area_finder: AreaFinder = AreaFinder(database.areas, database.positions)

    @classmethod
    def open(
        cls, database_path: Path | str | None = None, *, cache: DatabaseCache | None = None
    ) -> Self:
        """
        Open a codec on a database in read-only mode.

        Without arguments, the codec uses ``DatabaseCache.default()``, which is built on
        first use and extended with the points and shapes of each municipality looked up.
        Pass a configured ``cache`` to choose its directory, forbid downloads on use, or
        refresh it after an age.

        Parameters
        ----------
        database_path : Path | str | None
            SQLite file created by ``RegistryImporter``, used as it is, or ``None`` for a
            cache.
        cache : DatabaseCache | None
            Cache to use, or ``None`` for ``DatabaseCache.default()``.

        Returns
        -------
        Self
            Codec bound to the database.

        Raises
        ------
        ValueError
            If both ``database_path`` and ``cache`` are given.
        FileNotFoundError
            If the database file does not exist.
        UnsupportedDatabaseError
            If the file is not a database of this version of the library.
        DatasetNotImportedError
            If the cache has not been built and downloads are not allowed.
        RegistryDownloadError
            If the cache has to be built and a registry file cannot be downloaded.
        """
        if database_path is not None:
            if cache is not None:
                raise ValueError("Give either database_path or cache, not both.")
            return cls(AddressDatabase.open_read_only(database_path))
        selected_cache = DatabaseCache.default() if cache is None else cache
        return cls(AddressDatabase.open_read_only(selected_cache.ensure()), selected_cache)

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

    def list_area_imports(self) -> list[AreaImport]:
        """
        List the census boundary and registry map files imported into the database.

        Returns
        -------
        list[AreaImport]
            Imports from the oldest to the newest, with the numbers of stored and
            unmatched shapes.
        """
        return self._database.areas.list_imports()

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
            If the database contains no towns, or lot numbers are to be verified before
            any block, residence, or parcel master has been imported.
        RegistryDownloadError
            If the lots of the area have to be added to ``cache`` and a registry file
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
        if code.machiaza_id is None or not code.lot.numbers:
            return
        self._ensure_lots(code)
        positions = self._database.positions
        if not positions.is_lot_imported:
            raise DatasetNotImportedError(
                "No block, residence, or parcel master has been imported to verify lot numbers."
            )
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
            If the database contains no towns, or lot numbers are to be verified before
            any block, residence, or parcel master has been imported.
        RegistryDownloadError
            If the lots of the area have to be added to ``cache`` and a registry file
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
            the registry gives postal codes for only part of the towns.

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
            If the lots of the area have to be added to ``cache`` and a registry file
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
            If the lots of the area have to be added to ``cache`` and a registry file
            cannot be downloaded.
        """
        address_code = code if isinstance(code, AddressCode) else AddressCode.parse(code)
        self._ensure_lots(address_code)
        return self._locator.locate(address_code, crs)

    def _ensure_lots(self, code: AddressCode) -> None:
        if self._cache is not None and code.machiaza_id is not None and code.lot.numbers:
            self._cache.ensure_lots([code.lg_code])

    def find_nearest(
        self,
        coordinate: GeoCoordinate,
        crs: GeodeticCrs = GeodeticCrs.JGD2011,
        max_distance_meters: float = 1000.0,
    ) -> NearestAddress:
        """
        Find the address whose representative point is nearest to a coordinate.

        Blocks, residences, and parcels are preferred; the nearest town is returned only
        when no lot point is within ``max_distance_meters``. With a ``cache``, the lots
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
            If the lots of the area have to be added to ``cache`` and a registry file
            cannot be downloaded.
        """
        if self._cache is not None and max_distance_meters > 0:
            self._cache.ensure_lots(
                self._nearest_finder.list_nearby_municipalities(
                    coordinate, crs, max_distance_meters + self.NEARBY_LOT_MARGIN_METERS
                )
            )
        return self._nearest_finder.find(coordinate, crs, max_distance_meters)

    def find_area(self, address: str) -> AddressArea:
        """
        Find the shape of a free-form address.

        Parameters
        ----------
        address : str
            Address in any common notation.

        Returns
        -------
        AddressArea
            Shape of the address, or of its nearest enclosing area that has one.

        Raises
        ------
        ValueError
            If the address is blank.
        AddressNotFoundError
            If the address does not match a registered area.
        AmbiguousAddressError
            If the address fits several areas or lot numbers equally well.
        AreaNotFoundError
            If neither the address nor any enclosing area below the prefecture has a shape.
        DatasetNotImportedError
            If no town or no shape has been imported.
        RegistryDownloadError
            If the shapes of the municipality have to be added to ``cache`` and a file
            cannot be downloaded.
        """
        return self.find_area_code(self.encode(address))

    def find_area_code(self, code: AddressCode | str) -> AddressArea:
        """
        Find the shape of an address code.

        Towns take their shapes from the census boundaries and land parcels from the
        registry maps; blocks and residences of the residence indication have none and
        fall back to their town. With a ``cache``, the town boundaries of the
        municipality, and its registry maps for parcel numbers, are added first.

        Parameters
        ----------
        code : AddressCode | str
            Address code or its string form.

        Returns
        -------
        AddressArea
            Shape of the code, or of its nearest enclosing area that has one.

        Raises
        ------
        ValueError
            If a string code is malformed.
        AreaNotFoundError
            If neither the code nor any enclosing area below the prefecture has a shape.
        DatasetNotImportedError
            If no shape has been imported.
        RegistryDownloadError
            If the shapes of the municipality have to be added to ``cache`` and a file
            cannot be downloaded.
        """
        address_code = code if isinstance(code, AddressCode) else AddressCode.parse(code)
        if self._cache is not None and not AddressCode.is_prefecture_code(address_code.lg_code):
            self._cache.ensure_areas(
                [address_code.lg_code],
                is_parcel_included=self._area_finder.has_parcel_shape(address_code),
            )
        return self._area_finder.find(address_code)

    def find_areas_at(
        self,
        coordinate: GeoCoordinate,
        crs: GeodeticCrs = GeodeticCrs.JGD2011,
        *,
        is_parcel_included: bool = False,
    ) -> list[AddressArea]:
        """
        Find the towns, and optionally the land parcels, whose shapes contain a coordinate.

        With a ``cache``, the town boundaries of the municipalities whose town points lie
        within the first of ``NEARBY_AREA_RADII_METERS`` are added first, then within the
        next radius while no town contains the coordinate. Land parcel maps are added
        only for the municipalities of the containing towns.

        Parameters
        ----------
        coordinate : GeoCoordinate
            Coordinate on ``crs``.
        crs : GeodeticCrs
            Datum of ``coordinate``.
        is_parcel_included : bool
            Whether land parcels are listed besides towns.

        Returns
        -------
        list[AddressArea]
            Towns first, then land parcels; empty when no shape contains the coordinate.

        Raises
        ------
        DatasetNotImportedError
            If no shape has been imported.
        RegistryDownloadError
            If shapes have to be added to ``cache`` and a file cannot be downloaded.
        RuntimeError
            If ``crs`` cannot be transformed.
        """
        if self._cache is not None:
            self._ensure_areas_at(
                self._cache, coordinate, crs, is_parcel_included=is_parcel_included
            )
        return self._area_finder.list_at(coordinate, crs, is_parcel_included=is_parcel_included)

    def _ensure_areas_at(
        self,
        cache: DatabaseCache,
        coordinate: GeoCoordinate,
        crs: GeodeticCrs,
        *,
        is_parcel_included: bool,
    ) -> None:
        towns: list[AddressArea] = []
        for radius_meters in self.NEARBY_AREA_RADII_METERS:
            cache.ensure_areas(
                self._nearest_finder.list_nearby_municipalities(coordinate, crs, radius_meters),
                is_parcel_included=False,
            )
            if self._database.areas.is_area_imported:
                towns = self._area_finder.list_at(coordinate, crs, is_parcel_included=False)
            if towns:
                break
        if is_parcel_included:
            cache.ensure_areas({town.code.lg_code for town in towns}, is_parcel_included=True)
