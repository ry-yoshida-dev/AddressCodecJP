# AddressCodecJP

## Overview

AddressCodecJP normalizes free-form Japanese addresses and converts them to and from
stable **address codes** anchored to the town master (町字マスター) of the Digital
Agency's [Address Base Registry](https://www.digital.go.jp/policies/base_registry_address)
(ABR). Addresses and codes are also mapped to the ABR **representative points** (代表点)
down to residences and land parcels, and to **area shapes**: town polygons from the
census boundaries and land parcel polygons from the registry office maps. A coordinate
is mapped back to the nearest address and to the towns and parcels that contain it.

Requires Python 3.12+. Runtime dependencies are
[GeoCoordinate](https://github.com/ry-yoshida-dev/GeoCoordinate), NumPy, and platformdirs.

### Address code format

```
{lg_code}[-{machiaza_id}[-{block}[-{residence}]]]
```

| Code | Level | Address |
| --- | --- | --- |
| `130001` | Prefecture | 東京都 |
| `131016` | Municipality | 東京都千代田区 |
| `131016-0011000` | Town (oaza) | 東京都千代田区丸の内 |
| `131016-0011001` | Town (chome) | 東京都千代田区丸の内1丁目 |
| `131016-0011001-2` | Block | 東京都千代田区丸の内1丁目2番 |
| `131016-0011001-2-3` | Residence | 東京都千代田区丸の内1丁目2番3号 |

`lg_code` is the local government code (check digit validated), `machiaza_id` the ABR
town ID. Building names and room numbers are not encoded; they are returned as
`remainder`.

Oaza listed only by chome (丸の内 has 1丁目 to 3丁目) get an oaza-level code (`000`
chome part) on import. It never carries lot numbers.

## Setup

Add the repository to the dependencies of a project:

```toml
[project]
dependencies = [
    "address-codec-jp @ git+https://github.com/ry-yoshida-dev/AddressCodecJP.git@<commit>",
]
```

No database setup is needed. On first use, `AddressCodec.open()` downloads the
nationwide town master and the prefecture, municipality, and town points (about 15 MB)
from the ABR download site and builds a database (about 180 MB) in the user cache
directory. The block, residence, and land parcel points of a municipality are added the
first time an address there is located or verified, or a coordinate near it is
searched; its census town boundaries the first time an area there is looked up, and its
registry maps only when a parcel shape is needed.

The cache is a single SQLite file, `towns-v{schema version}.sqlite3`, e.g. in
`~/Library/Caches/address-codec-jp/` on macOS and `~/.cache/address-codec-jp/` on Linux.
A new schema version builds its own file and deletes the old ones.

### Using the cache in an application

`DatabaseCache` decides where the data lives and when it is downloaded; pass it to
`AddressCodec.open(cache=...)`.

```python
from datetime import timedelta
from pathlib import Path

from address_codec_jp import AddressCodec, DatabaseCache

# At build or deploy time, e.g. in a Dockerfile: download what the service needs.
DatabaseCache.default(directory=Path("/var/lib/addresses")).prepare(prefecture_codes=["13"])

# In the service: never download while handling requests.
cache = DatabaseCache.default(directory=Path("/var/lib/addresses"), is_download_allowed=False)
with AddressCodec.open(cache=cache) as codec:
    codec.locate("千代田区丸の内1-9-1")

# In a batch job: download on demand, and refresh data older than 30 days on open.
with AddressCodec.open(cache=DatabaseCache.default(max_age=timedelta(days=30))) as codec:
    codec.find_area("大阪市北区梅田3-1-1")
```

| Need | API |
| --- | --- |
| Choose the directory | `DatabaseCache.default(directory=...)`, or `ADDRESS_CODEC_JP_CACHE_DIR` |
| Download ahead of use | `prepare(prefecture_codes, municipality_codes, is_area_included=True, is_parcel_included=False)` |
| No downloads on use | `is_download_allowed=False`: a missing database raises `DatasetNotImportedError`; missing points and shapes fall back to the enclosing areas |
| Follow new releases | `max_age=timedelta(...)` refreshes on first use when older, keeping the current data with a warning if that fails; `refresh()` on demand |
| Inspect or delete | `describe()` returns a `CacheStatus`; `clear()` |
| See what it downloads | INFO records of the `address_codec_jp.caching.database_cache` logger |
| Mirror the download site | `ADDRESS_CODEC_JP_BASE_URL` |

Writes are serialized across processes by a lock file in the cache directory, so the
workers of a server can share one cache; readers wait up to two minutes while a
municipality is added. A codec must be used in the thread that opened it. `refresh`
replaces the file atomically; codecs opened before keep reading the old data until they
are closed. Building a database removes those of older schema versions but keeps newer
ones, so different versions of the library can share a directory.

The command line offers the same: `address-codec-jp cache [info|prepare|refresh|clear]`,
e.g. `address-codec-jp cache prepare --prefecture 13`. `--database PATH` works on a
database file of your own, filled by `download`, `import`, and `import-area`.

### Data sources

| Data | Source | Terms |
| --- | --- | --- |
| Town master, points | [Address Base Registry](https://www.digital.go.jp/policies/base_registry_address) (Digital Agency) | PDL 1.0; land parcels: 登記所備付地図データ利用規約 |
| Town polygons | [2020 census town boundaries](https://www.e-stat.go.jp/gis) (Statistics Bureau, e-Stat) | e-Stat terms of use (CC BY 4.0 compatible) |
| Parcel polygons | [Registry office maps](https://www.geospatial.jp/ckan/dataset/?q=登記所備付地図データ) (Ministry of Justice, G-Spatial Information Center) | 登記所備付地図データ利用規約 |

The data is downloaded by each user from these sources and converted locally; credit
the sources and the conversion when publishing results.

## Examples

### Python

```python
from geo_coordinate import GeoCoordinate

from address_codec_jp import AddressCodec, AddressFormat, LotStyle, NameScript, NumeralStyle

with AddressCodec.open() as codec:
    code = codec.encode("東京都千代田区丸の内１丁目２番３号")
    print(code, code.level.name)
    print(codec.decode(code, AddressFormat(numeral_style=NumeralStyle.KANJI)))
    print(codec.decode(code, AddressFormat(lot_style=LotStyle.HYPHEN, is_prefecture_included=False)))
    print(codec.decode(code, AddressFormat(name_script=NameScript.KATAKANA)))

    match = codec.match("千代田区丸の内2-4-1 丸ビル")
    print(match.code, match.remainder)

    location = codec.locate("千代田区丸の内1-9-1")
    print(location.located_code, location.level.name, location.is_exact)

    nearest = codec.find_nearest(GeoCoordinate.from_degrees(35.6812, 139.7671))
    print(nearest.code, codec.decode(nearest.code), f"{nearest.distance_meters:.1f}")

    area = codec.find_area("千代田区丸の内1-9-1")
    print(area.located_code, area.level.name, area.is_exact, area.shape.to_geojson()[:30])

    parcel = codec.find_area("埼玉県入間郡三芳町大字竹間沢585-1")
    print(parcel.located_code, parcel.is_exact, [source.name for source in parcel.sources])

    towns = codec.find_areas_at(GeoCoordinate.from_degrees(35.6812, 139.7671))
    print([str(town.code) for town in towns])
```

```
131016-0011001-2-3 RESIDENCE
東京都千代田区丸の内一丁目二番三号
千代田区丸の内1-2-3
トウキョウトチヨダクマルノウチ1チョウメ2バン3ゴウ
131016-0011002-4-1 丸ビル
131016-0011001-9 BLOCK False
131016-0011001-9 東京都千代田区丸の内1丁目9番 13.5
131016-0011001 TOWN False {"type":"MultiPolygon","coordi
113247-0003000-585-1 True ['REGISTRY_MAP']
['131016-0011001']
```

`locate` and `find_area` fall back to the nearest enclosing area that has a point or
shape; `is_exact` tells whether it is the address itself. An oaza or municipality
without a polygon of its own is made of the polygons of its towns. Shapes are on
JGD2011 and written as GeoJSON MultiPolygons. Output is from the datasets released in
October 2026.

### Command line

```bash
uv run address-codec-jp encode "千代田区丸の内一の二の三" "東京都千代田区"
uv run address-codec-jp decode 131016-0011001-2-3 --numeral kanji
uv run address-codec-jp locate "千代田区内幸町1-6-1" --crs wgs84
uv run address-codec-jp nearest 35.6812,139.7671
uv run address-codec-jp area "千代田区丸の内1-9-1"
uv run address-codec-jp area-at 35.6812,139.7671 --parcels --output jsonl
```

Commands read one input per line from standard input when no argument is given, and
`--output jsonl` writes one JSON object per input. Run `address-codec-jp <command> -h`
for the options.

## Errors

Every error derives from `AddressCodecError` and from a built-in exception.

| Error | Built-in base | Raised when |
| --- | --- | --- |
| `AddressNotFoundError` | `LookupError` | An address, code, or verified lot is not registered |
| `AmbiguousAddressError` | `LookupError` | Several areas fit equally well; `candidates` lists their codes |
| `PositionNotFoundError` | `LookupError` | No imported point fits |
| `AreaNotFoundError` | `LookupError` | No imported area shape fits |
| `ReadingNotFoundError` | `LookupError` | A katakana reading is not registered |
| `DatasetNotImportedError` | `RuntimeError` | A required dataset has not been imported |
| `RegistryFormatError` | `ValueError` | A registry file is malformed |
| `BoundaryFormatError` | `ValueError` | A census boundary or registry map file is malformed |
| `RegistryDownloadError` | `OSError` | A file cannot be downloaded |
| `UnsupportedDatabaseError` | `ValueError` | A database was not created by this version |

## Limitations

- Lot numbers are checked against the registry only with `is_lot_verified=True`.
- Kyoto-style street directions (`上る`/`西入`) are not interpreted.
- Town polygons are the census boundaries of October 2020. About 3% of them match no
  current town (renamed towns, merged areas, river beds) and are skipped; koaza without
  their own polygon fall back to their oaza.
- Blocks and residences of the residence indication have no published polygons and fall
  back to their town. Parcel polygons exist only for parcel-numbered towns and only for
  map sheets on public coordinates; many urban sheets are on arbitrary local
  coordinates and cannot be placed.
- Census boundaries and registry maps are surveyed separately, so their edges may
  disagree by a few meters.

## Development

```bash
uv run pytest
uv run ruff check src tests
uv run mypy src tests
uv run basedpyright
```
