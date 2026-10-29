# AddressCodecJP

## Overview

AddressCodecJP normalizes free-form Japanese addresses and converts them to and from
stable **address codes**. Codes are anchored to the town master (町字マスター) of the
[Address Base Registry](https://www.digital.go.jp/policies/base_registry_address)
(アドレス・ベース・レジストリ, ABR) published by the Digital Agency, so they stay valid
independently of how an address was written.

The library has no runtime dependencies beyond the Python standard library (3.12+).

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

- Full-width and half-width characters, leading postal codes (`〒100-0005`)
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
decides among them. After the municipality, every reading of oaza, chome, koaza, and lot
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

## Setup

1. Download the nationwide town master (日本 町字マスター データセット, about 12 MB zipped)
   from the [ABR download site](https://dataset.address-br.digital.go.jp/).
2. Import it into a SQLite database. The master has about 730,000 rows (156 MB as CSV),
   so it is indexed once instead of being parsed on every start. Import takes a few
   seconds and replaces the previous contents, so towns abolished in a newer master are
   removed. Rows repeated with identical contents (about 1,200 in the October 2026 master)
   are stored once; an ID repeated with different contents aborts the import:

```bash
uv sync
mkdir -p data
curl -o data/mt_town_all.csv.zip https://data.address-br.digital.go.jp/mt_town/mt_town_all.csv.zip
uv run address-codec-jp --database towns.sqlite3 import data/mt_town_all.csv.zip
```

The reader requires the columns `lg_code`, `machiaza_id`, `pref`, `county`, `city`,
`ward`, `oaza_cho`, `chome`, and `koaza`; other columns are ignored. Short rows and
malformed codes (including a wrong check digit) raise `ValueError`.

In Python, `AddressCodec.create(path)` creates a database for `import_town_master`, and
`AddressCodec.open(path)` opens an existing one read-only; it raises `FileNotFoundError`
for a missing file and `ValueError` for an SQLite file without the town table instead of
modifying it. Importing again through the same codec refreshes its matching indexes.

## Examples

### Python

```python
from address_codec_jp import AddressCodec, AddressFormat, LotStyle, NumeralStyle

with AddressCodec.open("towns.sqlite3") as codec:
    code = codec.encode("東京都千代田区丸の内１丁目２番３号")
    print(code)
    print(codec.decode(code))
    print(codec.decode(code, AddressFormat(numeral_style=NumeralStyle.KANJI)))
    print(codec.decode(code, AddressFormat(lot_style=LotStyle.HYPHEN, is_prefecture_included=False)))

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

### Command line

```bash
uv run address-codec-jp encode "千代田区丸の内一の二の三" "東京都台東区"
uv run address-codec-jp decode 131016-0011001-2-3 --numeral kanji --lot land_parcel
uv run address-codec-jp decode 131016-0011001-2-3 --lot hyphen --width full --no-prefecture
```

Decode options: `--numeral {arabic,kanji}`, `--lot {residence_indication,land_parcel,hyphen}`,
`--width {half,full}`, `--no-prefecture`, `--no-county`.

## Limitations

- Block and residence numbers are parsed but not validated against the ABR residence
  indication or land parcel masters.
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
- Oaza and koaza names are looked up by scanning all names of the municipality
  (about 0.7 ms per address on the nationwide master).

## Development

```bash
uv run pytest
uv run ruff check src tests
uv run mypy src tests
uv run basedpyright
```
