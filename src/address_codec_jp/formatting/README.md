# formatting

## Overview

Renders an `Address` (a prefecture, a municipality, or a town with lot numbers) as
address text in a selectable format, with registered names or their katakana readings.

## Components

| Component | Responsibility |
| --- | --- |
| [address_formatter.py](address_formatter.py) | `AddressFormatter`: builds the address string of an `Address` |
| [address_format.py](address_format.py) | `AddressFormat`: combination of output options |
| [numeral_style.py](numeral_style.py) | `NumeralStyle`: Arabic or kanji numerals |
| [lot_style.py](lot_style.py) | `LotStyle`: `番`/`号`, `番地`, or hyphen notation |
| [digit_width.py](digit_width.py) | `DigitWidth`: half-width or full-width digits |
| [name_script.py](name_script.py) | `NameScript`: registered names or katakana readings |

## Examples

| Format | Output |
| --- | --- |
| `AddressFormat()` | `東京都千代田区丸の内1丁目2番3号` |
| `numeral_style=NumeralStyle.KANJI` | `東京都千代田区丸の内一丁目二番三号` |
| `lot_style=LotStyle.LAND_PARCEL` | `東京都千代田区丸の内1丁目2番地3` |
| `lot_style=LotStyle.HYPHEN, digit_width=DigitWidth.FULL` | `東京都千代田区丸の内１－２－３` |
| `name_script=NameScript.KATAKANA` | `トウキョウトチヨダクマルノウチ1チョウメ2バン3ゴウ` |
| `is_postal_code_included=True` | `〒060-0042 北海道札幌市中央区大通西1丁目` (towns with one registered postal code) |
