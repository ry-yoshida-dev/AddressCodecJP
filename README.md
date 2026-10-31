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
[GeoCoordinate](https://github.com/ry-yoshida-dev/GeoCoordinate), NumPy, platformdirs, and
filelock; the optional [web API](#web-api) adds FastAPI and uvicorn (`api` extra).

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
town ID. Building names, floors, and room numbers are not encoded; they are returned as
`remainder`, as written in the input.

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
nationwide town master and the prefecture, municipality, and town points from the ABR
download site and builds a database in the user cache directory. The block, residence,
and land parcel points of a municipality are added the first time an address there is
located or verified, or a coordinate near it is searched; its census town boundaries the
first time an area there is looked up, and its registry maps only when a parcel shape is
needed. The database therefore grows with every municipality added; `describe()` or
`address-codec-jp cache info` reports its current size.

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
| No downloads on use | `is_download_allowed=False`: a missing database raises `DatasetNotImportedError`; missing points and shapes fall back to the enclosing areas; `max_age` cannot be combined with it |
| Follow new releases | `max_age=timedelta(...)` refreshes on first use when older, keeping the current data with a warning if downloading, reading, or writing fails; `refresh()` on demand |
| Inspect or delete | `describe()` returns a `CacheStatus`; `clear()` |
| See what it downloads | INFO records of the `address_codec_jp.database.cache` loggers |
| Mirror the download site | `ADDRESS_CODEC_JP_BASE_URL` |

Writes are serialized across processes by a lock file in the cache directory, so the
workers of a server can share one cache; readers wait up to two minutes while a
municipality is added. A codec must be used in the thread that opened it. `refresh`
replaces the file atomically; codecs opened before keep reading the old data until they
are closed, and once they would need data added they raise `DatabaseReplacedError` and
have to be opened again. A write interrupted by a killed process is rolled back the next
time the database is opened. Building a database removes those of older schema versions but keeps newer
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
    print(
        codec.decode(code, AddressFormat(lot_style=LotStyle.HYPHEN, is_prefecture_included=False))
    )
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

    print([codec.decode(child.code) for child in codec.list_children("131016-0011000")])

    print([codec.decode(area.code) for area in codec.list_by_name("府中市")])
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
['東京都千代田区丸の内1丁目', '東京都千代田区丸の内2丁目', '東京都千代田区丸の内3丁目']
['東京都府中市', '広島県府中市']
```

`locate` and `find_area` fall back to the nearest enclosing area that has a point or
shape; `is_exact` tells whether it is the address itself. An oaza or municipality
without a polygon of its own is made of the polygons of its towns. Shapes are on
JGD2011 and written as GeoJSON MultiPolygons, with exterior rings counterclockwise and
holes clockwise (RFC 7946). Output is from the datasets released in
October 2026.

Names before the town may be shortened: the prefecture (`千代田区丸の内`), the ward of a
designated city (`横浜市山下町`), its city (`中京区上本能寺前町`), or the whole
municipality (`霞が関1-1-1`). When the rest fits several areas, `AmbiguousAddressError`
lists them in `candidates`; a prefecture or postal code written with the address narrows
them down (`大阪府梅田3-1-1`), and so does an area code given as `within`
(`codec.encode("府中市", within="340006")` is 広島県府中市). `locate` and `find_area` take
`within` and `is_lot_verified` as `match` does. Lot numbers above
`LotNumber.MAX_NUMBER` and an address that is only a postal code raise `ValueError`.

Kyoto street directions (通り名) are read before the town name, as they are usually
written, or after it, as the registry lists them, also with variants such as `上ル` or
`通り`. Without lot numbers, the address is the street direction itself; lot numbers
belong to the town, so with them the code is that of the town, which locates the
residence or parcel. A street direction the registry does not list is skipped, and
decides between towns of the same name in the ward by the streets it names. The ward and
city may be omitted (`烏丸通塩小路下る東塩小路町`). A code of a street direction with lot
numbers, such as `261068-0416115-538-1`, is located, verified, and shaped as the same
lot numbers of its town.

```python
with AddressCodec.open() as codec:
    print(codec.encode("京都市下京区烏丸通塩小路下る東塩小路町"))
    print(codec.encode("京都市下京区烏丸通塩小路下ル東塩小路町721"))
    print(codec.decode("261068-0416115"))
```

```
261068-0416115
261068-0416000-721
京都府京都市下京区烏丸通塩小路下る東塩小路町
```

`match_group` reads addresses that all lie in one common area: the narrowest
prefecture, municipality, or town that encloses a candidate of every address decides
those ambiguous on their own. Next to `千代田区丸の内1-1`, `府中市` is 東京都府中市. The
group fails as a whole when that area is missing or not unique, or an address stays
ambiguous within it.

```python
with AddressCodec.open() as codec:
    group = codec.match_group(["千代田区丸の内1-1", "府中市"])
    print(group.area, [str(item.code) for item in group.matches])
```

```
130001 ['131016-0011001-1', '132063']
```

`list_children` lists the registered areas directly under a code, those whose `parent`
it is: the municipalities of a prefecture, with the wards of a designated city in place
of the city; the oaza of a municipality; and the chome and koaza of an oaza. Chome and
koaza whose oaza is not registered are listed under the municipality. Lot numbers are
not listed.

`list_by_name` lists every area that bears a name, where `match` would reject a shared
name as ambiguous: the prefecture, municipalities, oaza, and koaza whose whole name it
is, ignoring `ヶ`/`ケ`/`が` and a leading `大字`/`字` (`list_by_name("藤ヶ丘")` finds
every 藤が丘). Parts of names are not searched. A designated city stands for all its
wards, and a ward written alone for every ward of that name. A prefecture or
municipality before the name (`府中市宮町`), or `within`, narrows the result down. An
oaza is listed as its oaza-level code, or as its chome and koaza when the oaza itself is
not registered.

### Command line

```bash
uv run address-codec-jp encode "千代田区丸の内一の二の三" "東京都千代田区"
uv run address-codec-jp decode 131016-0011001-2-3 --numeral kanji
uv run address-codec-jp locate "千代田区内幸町1-6-1" --crs wgs84
uv run address-codec-jp nearest 35.6812,139.7671
uv run address-codec-jp children 130001
uv run address-codec-jp name 府中市 自由が丘
uv run address-codec-jp locate-code 131016-0011001-2-3
uv run address-codec-jp area "千代田区丸の内1-9-1"
uv run address-codec-jp area-code 131016-0011001 --no-geometry
uv run address-codec-jp areas-at 35.6812,139.7671 --parcels --output jsonl
```

Commands read one input per line from standard input when no argument is given. Every
input is represented on standard output: tab-separated lines start with the input, with
one line per result row, the input alone for an empty result, and `ERROR`, the error
type, and the message for a failure; `--output jsonl` writes one JSON object per input.
The exit status is 0 when every input was answered, 1 when some input failed, 2 for
invalid arguments, and 3 when the command could not run. Run
`address-codec-jp <command> -h` for the options.

## Web API

The `api` extra serves the codec over HTTP
(`address-codec-jp[api] @ git+https://...`). The service reads a cache prepared
beforehand and never downloads while handling requests; the application fails at
start when the cache has not been built.

```dockerfile
FROM python:3.13-slim
RUN pip install "address-codec-jp[api] @ git+https://github.com/ry-yoshida-dev/AddressCodecJP.git@<commit>"
ENV ADDRESS_CODEC_JP_CACHE_DIR=/var/lib/addresses
ENV ADDRESS_CODEC_JP_API_PUBLISHER="Example Maps Inc."
RUN address-codec-jp cache prepare --prefecture 13
CMD ["uvicorn", "--factory", "address_codec_jp.frontends.api:ApplicationFactory.from_environment", \
     "--host", "0.0.0.0", "--workers", "4"]
```

| Endpoint | Query |
| --- | --- |
| `GET /v1/codes?address=` | Encode; `verify_lot=true` checks the lot numbers |
| `GET /v1/codes/{code}` | Decode; `numeral`, `lot`, `width`, `prefecture`, `county`, `kana`, `postal_code` |
| `GET /v1/locations?address=`, `GET /v1/codes/{code}/location` | Representative point; `crs` |
| `GET /v1/nearest?coordinate=lat,lon` | Nearest address; `crs`, `max_distance` |
| `GET /v1/postal-codes/{postal_code}` | Towns of a postal code; format options as for decoding |
| `GET /v1/codes/{code}/children` | Areas directly under a prefecture, municipality, or oaza; format options as for decoding |
| `GET /v1/names/{name}` | Every area that bears a name; format options as for decoding |
| `GET /v1/areas?address=`, `GET /v1/codes/{code}/area` | Shape; `geometry=false` omits the GeoJSON |
| `GET /v1/areas-at?coordinate=lat,lon` | Containing towns; `parcels=true` adds parcels, `geometry=true` adds GeoJSON |
| `POST /v1/batch` | `{"operation": "locate", "inputs": [...]}` with the same options and defaults as the GET endpoint; operations are named like the commands (`locate-code`, `area-code`, `areas-at`, ...); per-input `status` on failure |
| `GET /health` | Readiness and the number of prepared municipalities |

Responses are the fields of the JSON Lines output plus `attribution`, the credits of
the datasets used. Errors are `{"error", "error_type"}` with status 404 (not found),
409 (ambiguous, with `candidates`), 400 (`InvalidRequestError`, also for parameters
or bodies that fail validation and inputs longer than the limit), or 503 (data not
prepared, or the database is being updated, with `Retry-After`); any other failure is logged and answered with a generic 500 body.
OpenAPI documentation is served at `/docs`.

| Variable | Default | Meaning |
| --- | --- | --- |
| `ADDRESS_CODEC_JP_API_PUBLISHER` | required | Organization that processes and serves the data, named in every credit |
| `ADDRESS_CODEC_JP_CACHE_DIR` | user cache directory | Prepared cache |
| `ADDRESS_CODEC_JP_API_THREADS` | `4` | Worker threads per process, each with its own codec |
| `ADDRESS_CODEC_JP_API_MAX_BATCH_SIZE` | `1000` | Inputs per batch request |
| `ADDRESS_CODEC_JP_API_MAX_INPUT_LENGTH` | `1000` | Characters per input; longer inputs are rejected with 400 |
| `ADDRESS_CODEC_JP_API_COVERAGE_REQUIRED` | `true` | Reject with 503 a query whose municipality lacks prepared lots, boundaries, or registry maps, instead of falling back to an enclosing area |

Scale with uvicorn worker processes; each thread holds its own codec and matching
indexes, so memory grows with the threads per worker. Run
`address-codec-jp cache prepare` or `cache refresh` on the same directory to extend or
update a running service: a replaced database is reopened by each worker thread before
its next query, so no restart is needed. With coverage required, a nearest address
requires the lots of every municipality that might hold a nearer lot, so a coordinate
near an unprepared municipality gives 503; parcel shapes require the registry maps of
their municipality; and a coordinate outside every prepared boundary gives 404.

Serving the data to third parties redistributes it in processed form, which the terms
of all three sources allow, commercially too: the Address Base Registry under the
Public Data License 1.0, the census boundaries under the e-Stat terms of use, and the
registry maps under the 登記所備付地図データ利用規約, which also cover the parcel master
and parcel points of the Address Base Registry. Each requires the source, the fact that
the data was processed, and who processed it, and forbids presenting the result as if
the government made it. `attribution` carries these credits in Japanese, following the
examples of the terms: the publisher is named in each, and registry maps are credited
per municipality with the date they were obtained. Parcel points are credited whenever
the town takes land parcel numbers. The terms of the registry maps forbid identifying
individuals by combining the data with other information, and the government accepts
no liability; `/docs` states these conditions to the users of the API.

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
| `DatabaseReplacedError` | `RuntimeError` | Data would be added for a codec whose database was replaced or removed; open it again |
| `RegistryFormatError` | `ValueError` | A registry file is malformed |
| `BoundaryFormatError` | `ValueError` | A census boundary or registry map file is malformed |
| `RegistryDownloadError` | `OSError` | A file cannot be downloaded |
| `UnsupportedDatabaseError` | `ValueError` | A database was not created by this version |

## Limitations

- Lot numbers are checked against the registry only with `is_lot_verified=True`.
- Kyoto street directions (`烏丸通塩小路下る`) are matched only in Kyoto, against the
  directions the registry lists; one that is not listed is skipped and only decides
  between towns of the same name. The same direction and town in two wards is
  ambiguous without the ward.
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
uv sync --all-extras
uv run pytest
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src tests
uv run basedpyright
```

CI runs these on Python 3.12 to 3.14. Record user-visible changes in
[CHANGELOG.md](CHANGELOG.md), and tag a release as `v{version}` after bumping `version`
in `pyproject.toml`.
