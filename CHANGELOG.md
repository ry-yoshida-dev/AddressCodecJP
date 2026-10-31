# Changelog

All notable changes are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/); before 1.0.0, a minor version may break
the API. The library is installed from git, so a version is a tagged commit
(`v0.1.0`).

## [Unreleased]

### Added

- Kyoto street directions (通り名) are matched before the oaza name, as Kyoto addresses
  are written (`烏丸通塩小路下る東塩小路町`), and after it, also with notation variants
  (`上ル`, `下がる`, `通り`, `入ル`), and the ward and city may be omitted. With lot
  numbers, the address is matched to the oaza, whose lot numbers the registry lists, so
  that it locates the residence or parcel. A direction the registry does not list
  decides between oaza of the same name by the streets it shares with theirs. Street
  directions are decoded before the oaza name, and a code of a street direction with
  lot numbers is verified, located, and shaped as the lot numbers of its oaza.
  `Town.is_street_direction` marks them, read from `koaza_aka_code` of the town master.
- Addresses written without the municipality (`霞が関1-1-1`, `東京都霞が関1-1-1`) or with
  a ward but without its designated city (`中京区上本能寺前町488`) are matched. A town
  name found in several municipalities raises `AmbiguousAddressError` with the
  candidates.
- `TownSource.map_oaza_names`, which custom town sources must now implement.
- `AddressCodec.list_children` lists the registered areas directly under a prefecture,
  municipality, or oaza, also as the `children` command, `GET /v1/codes/{code}/children`,
  and the `children` batch operation. `AddressCode.is_oaza` tells
  whether a code is an oaza-level town, and `AddressCode.is_lot` whether it has lot
  numbers.
- `AddressCodec.match` and `encode` take `within`, a prefecture, municipality, or town
  code the address must lie in.
- `AddressCodec.match_group` matches addresses that lie in one common area and returns a
  `GroupMatch`: the narrowest area enclosing a candidate of every address decides the
  addresses ambiguous on their own, and the group fails as a whole otherwise.
  `AreaMatcher.interpret` returns the failure of a match instead of raising it.
- `AddressCodec.list_by_name` lists every prefecture, municipality, oaza, and koaza that
  bears a name (`府中市`, `自由が丘`), where `match` rejects a shared name as ambiguous;
  also as the `name` command, `GET /v1/names/{name}`, and the `name` batch operation.
  `TownSource.list_town_names` and `list_towns_named`, which custom town sources must now
  implement.
- `AddressCodec.locate` and `find_area` take `within` and `is_lot_verified` as `match`
  does.
- `AddressCodec.list_nearby_municipalities` lists the municipalities whose lots
  `find_nearest` may return, and `AddressCodec.has_parcel_shape` tells whether the shape
  of a code comes from the registry maps.
- `DatabaseCache.open_database()` opens the cache for a codec, and
  `DatabaseReplacedError` (a `DatasetNotImportedError`) is raised when data would be
  added for a codec whose database was replaced or removed by `refresh` or `clear`; open
  the codec again.
- `locate-code` and `area-code` commands; `--no-geometry` for `area` and `area-code`,
  `--geometry` for `areas-at`; `decode` JSON Lines output includes `code`.
- `ADDRESS_CODEC_JP_API_MAX_INPUT_LENGTH` (default 1000) rejects longer inputs with 400.

### Changed

- **Breaking:** the database schema version is 7. Tables keyed by town are stored
  without row IDs and the numbering system as an integer, which makes the database
  considerably smaller, towns are indexed by oaza and koaza name for `list_by_name`,
  and towns record whether their koaza is a Kyoto street direction; a cache of an older
  version is rebuilt on first use.
- **Breaking:** the town master requires the `koaza_aka_code` column, `Town` requires
  `is_street_direction`, and custom town sources must implement
  `TownSource.list_street_municipality_codes`.
- **Breaking:** `AddressCodec` delegates to `AddressReader` (text matching),
  `AddressDirectory` (code lookup), and `Geocoder` (points, shapes, and the datasets
  added before a lookup). `NEARBY_LOT_MARGIN_METERS` and `NEARBY_AREA_RADII_METERS`
  moved from `AddressCodec` to `Geocoder`, which takes the `TownRepository` and any
  `DatasetSupplier` in place of `DatabaseCache`.
- Messages of `AmbiguousAddressError` for several towns list only the candidate towns.
- A designated city written without its ward and town (`〒231-0023 横浜市`) raises
  `AmbiguousAddressError` instead of being read as the ward of the postal code.
- **Breaking:** the progress of `DatabaseCache` is logged by the loggers under
  `address_codec_jp.database.cache` instead of only
  `address_codec_jp.database.cache.database_cache`; listen on the package logger.
- **Breaking:** modules sharing a prefix of three or more files moved into subpackages
  without the prefix: `frontends.api.query`, `database.storage.area`,
  `datasets.address_base_registry.lot`, and `results.address`. Prefixes repeating the
  directory were dropped: `database.cache.{directory,loader,status}` and
  `datasets.address_base_registry.{csv_file,csv_row,dataset,position_csv_reader,town_csv_reader}`.
  Class names are unchanged, and imports from the package `__init__` keep working.
- A number followed by a floor, building, or room marker (`5番地 3階`, `5 2F`,
  `7番地 2号館`, `101号室`) is no longer read as a lot number but left in `remainder`,
  and a town followed only by such a number (`一番町 3階`) is matched.
- **Breaking:** `AddressMatch.remainder` from `AddressCodec.match` and `match_group` is
  the text as written in the input instead of its normalized form, so spaces, widths,
  and kanji numerals of building names are kept (`ABC Building 5F`, `ハイツ一番館`).
- `DatabaseCache` delegates downloading and importing to the new `CacheLoader`.
- The command line interface is split into `ParserFactory`, `QueryAnswerer`, and
  `DatabaseMaintainer`.
- **Breaking:** lot numbers above `LotNumber.MAX_NUMBER` raise `ValueError` in
  addresses and codes, and the API answers them with 400 instead of 500.
- **Breaking:** `match_group` raises `TypeError` for a single string, and an address
  that is only a postal code raises `ValueError` saying so instead of calling it blank.
- **Breaking:** batch operations are named like the CLI commands: `locate-code`,
  `area-code`, `areas-at` (were `locate_code`, `area_code`, `areas_at`), and the CLI
  command `area-at` is renamed `areas-at`. `areas-at` on the command line omits
  geometries unless `--geometry` is given, as the API does.
- **Breaking:** CLI tab-separated output starts every line with the input, writes
  errors to standard output as `input<TAB>ERROR<TAB>type<TAB>message`, and writes the
  input alone for an empty result. Exit statuses are 0 when every input was answered, 1
  when some input failed, 2 for invalid arguments, and 3 when the command could not run.
  A CLI input failing with any library or database error is reported in place and the
  next input is processed.
- **Breaking:** `max_age` together with `is_download_allowed=False` raises `ValueError`.
- With coverage required, a nearest address requires the lots of every municipality
  that might hold a nearer lot; parcel shapes and `areas-at?parcels=true` require the
  registry maps of their municipality.
- GeoJSON output follows the RFC 7946 ring orientation: exteriors counterclockwise,
  holes clockwise.
- **Breaking:** `frontends.api.FileSignature` is removed; `CodecPool` and
  `OpenedCodec` use `database.cache.DatabaseFileSignature`.
- **Breaking:** the command line and the web API answer queries through one
  `frontends.query.QueryRunner`, so they read the same datasets and give the same
  fields. `QueryOperation` and `QueryOptions` moved from `frontends.api` to
  `frontends.query`. Each front end plugs in a `TextInterpreter`, which reports
  malformed inputs, and a `QueryGuard`, which decides the datasets a query may read: the
  command line uses `DirectInterpreter` and `PassThroughGuard`, and the web API
  `InputInterpreter` with `CoverageGuard` when coverage is required. A `QueryRecord`
  holds the fields, the tab-separated rows, built only when written, and the lot and
  shapes the answer used.
  `frontends.cli.QueryAnswerer`, `frontends.api.QueryResult`, and the duplicated
  dispatch of `QueryHandler` are removed, and `RecordWriter.write` takes a
  `QueryRecord`.
- The JSON Lines of `children` and `name` include the `code` and `name` fields, as in
  the web API, and `postal`, `name`, and `areas-at` report nothing found with the same
  message in both.
- **Breaking:** `frontends.cli.Command` is replaced by `MaintenanceCommand`, which holds
  `import`, `import-area`, `download`, `info`, and `cache`; `CommandArguments.command`
  is a `MaintenanceCommand` or a `QueryOperation`, set by every sub-command parser.
- **Breaking:** `ResultSerializer.towns`, `listed_areas`, and `areas` return the entries
  of a listing instead of a field named after it. `ResultSerializer.render` and
  `render_all` render addresses once as `RenderedAddress`, which `decoded`, `towns`, and
  `listed_areas` take, and `nearest` takes the rendered address. `children` and `named`
  are removed. `ResultRows` writes the tab-separated rows of the command line from the
  same results.
- `AddressCodec.verify_lot` checks the lot numbers of a code, as `match` does with
  verification, so the web API verifies a match without matching it twice.
- `AddressCodec.DEFAULT_MAX_DISTANCE_METERS` is the default largest distance of a
  nearest address in the library, the command line, and the web API.

### Fixed

- A cache directory shared with other files no longer loses them: only working
  directories that the cache marked are removed as stale, not any `build-*` directory,
  and `clear` deletes only the database and its journal files, not every file named
  after it, such as a `.bak` copy.
- Whitespace between a number and a following kanji numeral no longer joins them
  (`一番町5 一番館` was read without its lot number, `丸の内1-2 三号` as `1-23`).
- Opening a database after a writer was killed rolls back its interrupted write instead
  of failing with "not an SQLite database"; a database that stays locked raises
  `sqlite3.OperationalError`.
- A census boundary response that is not a ZIP archive, such as a maintenance page,
  raises `RegistryDownloadError` instead of being recorded as unpublished.
- The registry maps of a municipality are imported in one transaction, so a failed
  archive no longer leaves the municipality marked as imported; broken archives raise
  `BoundaryFormatError`.
- A refresh on first use after `max_age` keeps the current data with a warning on any
  download, format, or storage failure. The import ledger is reread when the database
  file changes.
- API request validation errors are answered with 400 `InvalidRequestError` in the
  `{"error", "error_type"}` format instead of 422; batch options default as for the GET
  endpoint of the operation.
- A deleted cache database is answered with 503, `/health` included, and a database
  locked by another process with 503 and `Retry-After`. Shutting down the API stops its
  worker threads even when one is busy.

## [0.1.0]

### Added

- Normalization of free-form Japanese addresses and conversion between addresses and
  address codes anchored to the town master of the Address Base Registry.
- Representative points of prefectures, municipalities, towns, blocks, residences, and
  land parcels, and the nearest address to a coordinate.
- Town polygons from the 2020 census boundaries and land parcel polygons from the
  registry office maps, and the areas that contain a coordinate.
- Postal code lookup, katakana readings, and lot number verification.
- `DatabaseCache`, which builds the database on first use, adds municipalities on
  demand, and can be prepared ahead of time, refreshed, and used offline.
- The `address-codec-jp` command line interface and an optional web API (`api` extra).

[Unreleased]: https://github.com/ry-yoshida-dev/AddressCodecJP/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ry-yoshida-dev/AddressCodecJP/releases/tag/v0.1.0
