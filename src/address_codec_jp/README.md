# address_codec_jp

## Overview

Public package of AddressCodecJP. `AddressCodec` is the facade that combines
normalization, town matching, lot number parsing, storage, formatting, and positioning.

## Components

| Component | Responsibility |
| --- | --- |
| [address_codec.py](address_codec.py) | `AddressCodec` facade: import, match, encode, decode, locate |
| [\_\_main\_\_.py](__main__.py) | `python -m address_codec_jp` entry point |
| [domain/](domain/) | Immutable domain models such as `AddressCode` and `Town` |
| [normalization/](normalization/) | Text normalization, kanji numerals, lot number parsing |
| [matching/](matching/) | Longest-prefix matching from text to a registered town |
| [storage/](storage/) | ABR CSV readers and SQLite town and position repositories |
| [positioning/](positioning/) | Representative point lookup with fallback and datum transformation |
| [formatting/](formatting/) | Output format options and address rendering |
| [cli/](cli/) | Command line interface |

## Examples

```python
from address_codec_jp import AddressCodec

with AddressCodec.open("towns.sqlite3") as codec:
    print(codec.encode("千代田区丸の内1-2-3"))
```
