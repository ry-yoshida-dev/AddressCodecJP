# AddressCodecJP

## Overview

AddressCodecJP normalizes free-form Japanese addresses and converts them to and from
stable **address codes** anchored to the town master (町字マスター) of the Digital
Agency's [Address Base Registry](https://www.digital.go.jp/policies/base_registry_address)
(ABR). Addresses and codes are also mapped to the ABR **representative points** (代表点),
and a coordinate is mapped back to the nearest address.

Requires Python 3.12+. Runtime dependencies are
[GeoCoordinate](https://github.com/ry-yoshida-dev/GeoCoordinate) and NumPy.

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

```bash
uv sync
uv run address-codec-jp --database towns.sqlite3 download data --prefecture 13 --import
```

This downloads the nationwide town master, prefecture and municipality points, and the
town, block, and residence files of Tokyo, and imports them into `towns.sqlite3`.
`--municipality LG_CODE` adds land parcel files. Files already downloaded can be imported
with `import`, and `info` lists what a database was built from.

## Examples

### Python

```python
from geo_coordinate import GeoCoordinate

from address_codec_jp import AddressCodec, AddressFormat, LotStyle, NameScript, NumeralStyle

with AddressCodec.open("towns.sqlite3") as codec:
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
```

```
131016-0011001-2-3 RESIDENCE
東京都千代田区丸の内一丁目二番三号
千代田区丸の内1-2-3
トウキョウトチヨダクマルノウチ1チョウメ2バン3ゴウ
131016-0011002-4-1 丸ビル
131016-0011001-9 BLOCK False
131016-0011001-9 東京都千代田区丸の内1丁目9番 13.5
```

`locate` falls back to the nearest enclosing area that has a point; `is_exact` tells
whether the point is the address itself. Output is from the Tokyo datasets released in
October 2026.

### Command line

```bash
uv run address-codec-jp encode "千代田区丸の内一の二の三" "東京都千代田区"
uv run address-codec-jp decode 131016-0011001-2-3 --numeral kanji
uv run address-codec-jp locate "千代田区内幸町1-6-1" --crs wgs84
uv run address-codec-jp nearest 35.6812,139.7671
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
| `ReadingNotFoundError` | `LookupError` | A katakana reading is not registered |
| `DatasetNotImportedError` | `RuntimeError` | A required dataset has not been imported |
| `RegistryFormatError` | `ValueError` | A registry file is malformed |
| `UnsupportedDatabaseError` | `ValueError` | A database was not created by this version |

## Limitations

- Lot numbers are checked against the registry only with `is_lot_verified=True`.
- Kyoto-style street directions (`上る`/`西入`) are not interpreted.
- Only representative points are provided, not area shapes.

## Development

```bash
uv run pytest
uv run ruff check src tests
uv run mypy src tests
uv run basedpyright
```
