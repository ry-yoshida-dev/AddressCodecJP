# Changelog

All notable changes are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/); before 1.0.0, a minor version may break
the API. The library is installed from git, so a version is a tagged commit
(`v0.1.0`).

## [Unreleased]

### Added

- Addresses written without the municipality (`霞が関1-1-1`, `東京都霞が関1-1-1`) or with
  a ward but without its designated city (`中京区上本能寺前町488`) are matched. A town
  name found in several municipalities raises `AmbiguousAddressError` with the
  candidates.
- `TownSource.map_oaza_names`, which custom town sources must now implement.

### Changed

- **Breaking:** the database schema version is 5. Tables keyed by town are stored
  without row IDs and the numbering system as an integer, which makes the database
  considerably smaller; a cache of version 4 is rebuilt on first use.
- Messages of `AmbiguousAddressError` for several towns list only the candidate towns.
- **Breaking:** the progress of `DatabaseCache` is logged by the loggers under
  `address_codec_jp.database.cache` instead of only
  `address_codec_jp.database.cache.database_cache`; listen on the package logger.
- **Breaking:** modules sharing a prefix of three or more files moved into subpackages
  without the prefix: `frontends.api.query`, `database.storage.area`,
  `datasets.address_base_registry.lot`, and `results.address`. Prefixes repeating the
  directory were dropped: `database.cache.{directory,loader,status}` and
  `datasets.address_base_registry.{csv_file,csv_row,dataset,position_csv_reader,town_csv_reader}`.
  Class names are unchanged, and imports from the package `__init__` keep working.
- `DatabaseCache` delegates downloading and importing to the new `CacheLoader`.
- The command line interface is split into `ParserFactory`, `QueryAnswerer`, and
  `DatabaseMaintainer`; the commands and their options are unchanged.

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
