# AddressCodecJP

## Overview

AddressCodecJP normalizes free-form Japanese addresses and converts them to and from
stable **address codes**. Codes are anchored to the town master (町字マスター) of the
[Address Base Registry](https://www.digital.go.jp/policies/base_registry_address)
(アドレス・ベース・レジストリ, ABR) published by the Digital Agency, so they stay valid
independently of how an address was written.

Addresses and codes are also mapped to **representative points** (代表点) published in the
position extensions (位置参照拡張) of the ABR, from the prefecture down to the residence or
land parcel, and a coordinate is mapped back to the address with the nearest point.
Decoded addresses can be written in katakana readings and with the registered postal
code. Points are returned as `GeoCoordinate` of
[GeoCoordinate](https://github.com/ry-yoshida-dev/GeoCoordinate), which is the only runtime
dependency (Python 3.12+).

### Address code format

```
{lg_code}[-{machiaza_id}[-{block}[-{residence}]]]
```

| Example | Level | Address |
| --- | --- | --- |
| `130001` | Prefecture | 東京都 |
| `131067` | Municipality | 東京都台東区 |
| `131067-0004000` | Oaza | 東京都台東区浅草橋 |
| `131067-0004001` | Chome | 東京都台東区浅草橋1丁目 |
| `131067-0004001-2-3` | Chome with lot numbers | 東京都台東区浅草橋1丁目2番3号 |

| Part | Meaning |
| --- | --- |
| `lg_code` | Six-digit local government code (全国地方公共団体コード); the check digit is validated. Prefecture codes have `000` in the third to fifth digits |
| `machiaza_id` | Seven-digit ABR town ID: a four-digit oaza part and a three-digit chome part |
| `block` | `番` or `番地` number (optional) |
| `residence` | `号` or branch number (optional) |

`AddressCode.level` tells the granularity as an `AddressLevel`. Building names and room
numbers are not encoded; they are returned as `remainder`.

The ABR lists some oaza only by chome (e.g. 浅草橋 has only 1丁目 to 5丁目). On import,
an oaza-level town with the chome part `000` is added for each such oaza so that addresses
ending at the oaza can be encoded. Such a town has `Town.is_registered == False` and never
carries lot numbers, because lot numbers of that oaza belong to one of its chome:
`台東区浅草橋6-1-1` raises `LookupError`, and decoding `131067-0004000-1-2` raises
`ValueError`.

### Normalization and matching

Input is normalized before matching:

- Full-width and half-width characters, leading postal codes (`〒100-0005`); the postal
  code is kept as `AddressMatch.postal_code`
- Spaces are removed, except that a space between digits becomes a separator
  (`本市１ 12番3号` reads koaza `１` and lot `12-3`)
- Kanji numerals before `丁目`/`番`/`号`/`条`/`の`/`-`, and at the end of the address
  (`一丁目二番三号`, `一の二の三`, `二番地三`, `二十三`, `一〇二`). A run that is valid
  only without its leading `一` keeps that `一` as the end of the name
  (`白旗九ノ一十二番` reads koaza `白旗九ノ一` and lot `12`)
- Dash look-alikes: `－ ‐ − – — ー` and `一` between digits, repeated dashes
- `1-2-3`, `1丁目2番3号`, `1丁目2番地3`, `2番地の3`, `1の2の3`

The registry sometimes registers names that differ only by `大字`/`字`, by `の`/`ノ`, or by
`ヶ`/`ケ`/`が` as different towns (e.g. 網走市 `大曲` and `字大曲`). Names are therefore
compared in three tiers: exact, ignoring `大字`/`字`, and folding notation variants and
old-style kanji. A stricter tier wins over a looser one.

A municipality may be written without its prefecture or county (`台東区`), the prefecture
without `都`/`府`/`県` (`東京千代田区`), and a designated city without its ward
(`横浜市山下町`). When such a name fits several municipalities (`府中市`), the town name
decides among them. The longest municipality name is tried first; when no town of it
matches the rest, shorter municipality names are tried, and a town name must then confirm
the municipality. After the municipality, every reading of oaza, chome, koaza, and lot
numbers is tried. Readings that leave less unparsed text win, then readings that explain more of the
text by registered names, then stricter comparisons. `LookupError` is raised instead of
guessing when:

- the municipality name is shared by several municipalities and no town name tells them
  apart (`府中市`, `府中市1-1`, `横浜市`)
- the best readings point to different towns, e.g. two towns registered under the same
  name, or a numeric koaza next to a lot number (`門前町本市112番3号`, `門前町椎木12-3`)
- a chome is written that does not exist (`丸の内9丁目`, `丸の内9-1-2`)
- digits are left unread without lot numbers (`浅草橋6-1-1` must not become `浅草` +
  `橋6-1-1`)

A leading postal code decides only these cases, among the municipalities or towns that
have it registered: `〒060-0042 札幌市` is 札幌市中央区. It never overrides the written
names, and the registry gives postal codes for only about 13% of the towns.

With `is_lot_verified=True`, `match` and `encode` also require the lot numbers to be
registered in the imported block, residence, or parcel masters. Without a residence number,
any residence of the block counts.

### Representative points

`AddressCodec.locate` returns an `AddressLocation`. When the registry has no point for the
address itself, the point of the nearest enclosing area is returned instead, in this order:
residence (`号`) or sub-parcel → block (`番`) or parcel (`番地`) → town → oaza (for a chome
or koaza) → municipality → prefecture. `located_code` and `level` tell which area the point
stands for, and `is_exact` whether it is the address itself. `latitude_degrees` and
`longitude_degrees` give the point as floats, and `coordinate` as a `GeoCoordinate`.

Whether `1番2号` is looked up as a residence indication or as a land parcel follows the
`rsdt_addr_flg` of the town, since residence indication towns also keep parcel numbers.

The registry publishes points on JGD2000 or JGD2011, mixed even within one file. They are
stored as published and transformed to the requested datum (JGD2011 by default) by
`DatumTransformation` of GeoCoordinate.

`AddressCodec.find_nearest` returns the block, residence, or parcel whose point is
nearest to a coordinate, or the nearest town when no lot point is within
`max_distance_meters` (1000 m by default), as a `NearestAddress` with the distance.
Representative points are not areas, so the nearest point may belong to the neighboring
lot or town.

### Readings and postal codes

`AddressFormat(name_script=NameScript.KATAKANA)` writes the registered katakana
readings (`トウキョウトチヨダクマルノウチ1チョウメ2バン3ゴウ`) and raises `LookupError` for a
town whose reading is not registered. `is_postal_code_included=True` writes the postal
code first (`〒060-0042 北海道札幌市中央区大通西1丁目`) for towns with exactly one
registered postal code. Oaza-level towns added on import take the postal codes of their
chome.

## Setup

1. Download the nationwide town master (日本 町字マスター データセット, about 12 MB zipped)
   from the [ABR download site](https://dataset.address-br.digital.go.jp/).
2. Import it into a SQLite database. The master has about 730,000 rows (156 MB as CSV),
   so it is indexed once instead of being parsed on every start. Import takes about
   seven seconds, makes a database of about 90 MB, and replaces the previous contents,
   so towns removed from a newer master are removed together with their imported points.
   Rows with an abolition date are skipped. Rows repeated with identical contents (about
   1,200 in the October 2026 master) are stored once; an ID repeated with different
   contents aborts the import:

```bash
uv sync
mkdir -p data
curl -o data/mt_town_all.csv.zip https://data.address-br.digital.go.jp/mt_town/mt_town_all.csv.zip
uv run address-codec-jp --database towns.sqlite3 import data/mt_town_all.csv.zip
```

The reader requires the columns `lg_code`, `machiaza_id`, `pref`, `county`, `city`,
`ward`, `oaza_cho`, `chome`, `koaza`, their readings `pref_kana`, `county_kana`,
`city_kana`, `ward_kana`, `oaza_cho_kana`, `chome_kana`, and `koaza_kana`, and
`post_code` and `ablt_date`; other columns are ignored. Short rows and malformed codes
(including a wrong check digit) raise `ValueError`.

In Python, `AddressCodec.create(path)` creates a database for `import_town_master`, and
`AddressCodec.open(path)` opens an existing one read-only; it raises `FileNotFoundError`
for a missing file and `ValueError` for an SQLite file without the town table, or one
created by an older version, instead of modifying it. Importing again through the same codec refreshes its matching indexes.
A codec holds one SQLite connection and must be used only in the thread that opened it;
open one codec per thread instead of sharing it.

### Representative points

Download the position-related datasets from the ABR download site and import them with
`import-positions`. Points are added to the same database, and files can be added
prefecture by prefecture in any order; rows with the same identifiers are replaced.

| Dataset | Unit of distribution | URL path under `https://data.address-br.digital.go.jp/` |
| --- | --- | --- |
| Prefecture points | Nationwide | `mt_pref_pos/mt_pref_pos_all.csv.zip` |
| Municipality points | Nationwide | `mt_city_pos/mt_city_pos_all.csv.zip` |
| Town points | Prefecture | `mt_town_pos/pref/mt_town_pos_pref{NN}.csv.zip` |
| Blocks and their points | Prefecture | `mt_rsdtdsp_blk/pref/mt_rsdtdsp_blk_pref{NN}.csv.zip`, `mt_rsdtdsp_blk_pos/pref/mt_rsdtdsp_blk_pos_pref{NN}.csv.zip` |
| Residences and their points | Prefecture | `mt_rsdtdsp_rsdt/pref/mt_rsdtdsp_rsdt_pref{NN}.csv.zip`, `mt_rsdtdsp_rsdt_pos/pref/mt_rsdtdsp_rsdt_pos_pref{NN}.csv.zip` |
| Parcels and their points | Municipality | `mt_parcel/city/mt_parcel_city{lg_code}.csv.zip`, `mt_parcel_pos/city/mt_parcel_pos_city{lg_code}.csv.zip` |

Blocks, residences, and parcels need both the number master and its position extension,
because the extension identifies a lot only by its registry ID. The dataset is identified
by the CSV header, so files may be renamed.

```bash
mkdir -p data/positions
base=https://data.address-br.digital.go.jp
for dataset in mt_pref_pos/mt_pref_pos_all mt_city_pos/mt_city_pos_all \
    mt_town_pos/pref/mt_town_pos_pref13 \
    mt_rsdtdsp_blk/pref/mt_rsdtdsp_blk_pref13 mt_rsdtdsp_blk_pos/pref/mt_rsdtdsp_blk_pos_pref13 \
    mt_rsdtdsp_rsdt/pref/mt_rsdtdsp_rsdt_pref13 mt_rsdtdsp_rsdt_pos/pref/mt_rsdtdsp_rsdt_pos_pref13; do
  curl -o "data/positions/${dataset##*/}.csv.zip" "$base/$dataset.csv.zip"
done
uv run address-codec-jp --database towns.sqlite3 import-positions data/positions/*.zip
```

Tokyo (about 1.75 million residences) takes about 20 seconds to import and adds about
610 MB to the database, including the coordinate index used by `find_nearest`. Lots
that a newer number master marks abolished (`ablt_date`) are removed on import.

On the Tokyo datasets, `locate` takes about 0.2 ms and `find_nearest` about 1 to 3 ms.

## Examples

### Python

```python
from address_codec_jp import AddressCodec, AddressFormat, LotStyle, NumeralStyle

with AddressCodec.open("towns.sqlite3") as codec:
    code = codec.encode("東京都千代田区丸の内１丁目２番３号")
    print(code)
    print(codec.decode(code))
    print(codec.decode(code, AddressFormat(numeral_style=NumeralStyle.KANJI)))
    print(
        codec.decode(code, AddressFormat(lot_style=LotStyle.HYPHEN, is_prefecture_included=False))
    )

    for address in ["東京都", "台東区", "台東区浅草橋"]:
        address_code = codec.encode(address)
        print(address_code, address_code.level.name, codec.decode(address_code))

    match = codec.match("港区六本木6-10-1 六本木ヒルズ森タワー")
    print(match.code, match.remainder)
```

```
131016-0011001-2-3
東京都千代田区丸の内1丁目2番3号
東京都千代田区丸の内一丁目二番三号
千代田区丸の内1-2-3
130001 PREFECTURE 東京都
131067 MUNICIPALITY 東京都台東区
131067-0004000 TOWN 東京都台東区浅草橋
131032-0028006-10-1 六本木ヒルズ森タワー
```

Output above is from the ABR town master released in October 2026.

```python
from geo_coordinate import GeodeticCrs

from address_codec_jp import AddressCodec

with AddressCodec.open("towns.sqlite3") as codec:
    for address in ["千代田区内幸町1-6-1", "千代田区丸の内1-9-1", "台東区浅草橋"]:
        location = codec.locate(address)
        print(location.located_code, location.level.name, location.is_exact)
        print(location.latitude_degrees, location.longitude_degrees)

    print(codec.locate_code("131016-0001001-6-1", GeodeticCrs.WGS84).crs)
```

```
131016-0001001-6-1 RESIDENCE True
35.668760794 139.758121483
131016-0011001-9 BLOCK False
35.681252 139.767235
131067 MUNICIPALITY False
35.712607 139.779984
EPSG:4326
```

Output above is from the Tokyo datasets released in October 2026.

```python
from geo_coordinate import GeoCoordinate

from address_codec_jp import AddressCodec, AddressFormat, NameScript

with AddressCodec.open("towns.sqlite3") as codec:
    print(codec.encode("〒060-0042 札幌市大通西1丁目"))
    print(codec.encode("〒060-0042 札幌市"))
    code = codec.encode("鳥取市面影1丁目1-1")
    print(codec.decode(code, AddressFormat(name_script=NameScript.KATAKANA)))
    print(codec.decode("011011-0002001", AddressFormat(is_postal_code_included=True)))
    print(codec.encode("鳥取市面影1丁目1-1", is_lot_verified=True))
    nearest = codec.find_nearest(GeoCoordinate.from_degrees(35.4804, 134.2459))
    print(nearest.code, codec.decode(nearest.code), f"{nearest.distance_meters:.1f}")
```

```
011011-0002001
011011
トットリケントットリシオモカゲ1チョウメ1バン1ゴウ
〒060-0042 北海道札幌市中央区大通西1丁目
312011-0055001-1-1
312011-0055001-1-1 鳥取県鳥取市面影1丁目1番1号 6.6
```

Output above is from the town master released in October 2026 and the Tottori datasets
(`pref31`) of the same release.

### Command line

```bash
uv run address-codec-jp encode "千代田区丸の内一の二の三" "東京都台東区"
uv run address-codec-jp decode 131016-0011001-2-3 --numeral kanji --lot land_parcel
uv run address-codec-jp decode 131016-0011001-2-3 --lot hyphen --width full --no-prefecture
```

Decode options: `--numeral {arabic,kanji}`, `--lot {residence_indication,land_parcel,hyphen}`,
`--width {half,full}`, `--no-prefecture`, `--no-county`, `--kana`, `--postal-code`.
Encode option: `--verify-lot`.

```bash
uv run address-codec-jp locate "千代田区内幸町1-6-1" "台東区浅草橋" --crs wgs84
```

```
131016-0001001-6-1	131016-0001001-6-1	RESIDENCE	35.668760794	139.758121483	EPSG:4326
131067-0004000	131067	MUNICIPALITY	35.712607000	139.779984000	EPSG:4326
```

Columns: requested code, located code, level, latitude, longitude, and datum.
Locate options: `--crs {tokyo,jgd2000,jgd2011,wgs84}`.

```bash
uv run address-codec-jp nearest 35.4804,134.2459
```

```
312011-0055001-1-1	鳥取県鳥取市面影1丁目1番1号	RESIDENCE	35.480365560	134.245840371	6.6	EPSG:6668
```

Columns: code, address, level, latitude, longitude, distance in meters, and datum.
Nearest options: `--crs`, `--max-distance` (meters, 1000 by default).

Query commands (`encode`, `decode`, `locate`, `nearest`) read one input per line from
standard input when no argument is given. `--output jsonl` writes one JSON object per
input, with errors as `{"input": ..., "error": ...}` in the same position, while the
default `tsv` writes errors to standard error. The exit status is 1 when any input fails.

```bash
printf '鳥取市面影1丁目1-1\n府中市\n' | uv run address-codec-jp encode --output jsonl
```

```
{"input": "鳥取市面影1丁目1-1", "code": "312011-0055001-1-1", "level": "TOWN", "remainder": ""}
{"input": "府中市", "error": "Municipality '府中市' is ambiguous: 東京都府中市, 広島県府中市. Add the prefecture or ward."}
```

## Limitations

- Block and residence numbers are validated only with `is_lot_verified=True`, and only
  against the masters that have been imported. Residences with a second residence number
  and parcels with a third number are not imported, so `2番4号` is rejected when the
  registry lists only `2番4号の1`.
- Kyoto-style street directions (`通`/`上る`/`西入`) and Hokkaido/Iwate special
  notations other than `条` and `地割` are not interpreted.
- A designated-city ward is matched only together with its city (`大阪市北区`);
  `北区` alone means the special ward of Tokyo. A designated city itself
  (`神奈川県横浜市`) has no code, because the town master lists only its wards.
- Lot numbers written in kanji right after a name that ends in a kanji numeral
  (`福井八十二番三号` with koaza `八`) cannot be split reliably and raise `LookupError`;
  write them with Arabic digits.
- An address that has no lot numbers but a building name with digits
  (`浅草橋1丁目 ビル3F`) is rejected, because the digits cannot be told apart from
  unread lot numbers.
- In hyphen notation, `春光台１条12-3` reads as chome 12 when that chome exists.
- The first address in each municipality builds its name index (a few milliseconds);
  later addresses take about 0.07 ms each on the nationwide master.
- Katakana readings of the oaza are missing in about 13,000 rows of the October 2026
  master. Romaji readings are not provided, because about 150,000 rows lack them.
- `find_nearest` ranks points on their published datum, which differs from JGD2011 by up
  to several meters near the 2011 Tohoku earthquake; the reported distance uses the
  transformed point.
- Only representative points are provided; the ABR polygon columns (`plygn_*`) are empty
  in the current releases, so areas are not returned as shapes.
- Oaza-level towns added on import (e.g. `台東区浅草橋`) have no published point and are
  located at their municipality.
- Residences with a second residence number and parcels with a third number cannot be
  expressed as address codes and are not imported.
- JGD2000 points are transformed to JGD2011 without the Tohoku correction grid
  (`touhokutaiheiyouoki2011.gsb`) unless PROJ has it installed, so points in the area of
  the 2011 Tohoku earthquake can be off by several meters.

## Development

```bash
uv run pytest
uv run ruff check src tests
uv run mypy src tests
uv run basedpyright
```
