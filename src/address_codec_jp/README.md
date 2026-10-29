# address_codec_jp

## Overview

Public package of AddressCodecJP. `RegistryImporter` imports registry datasets into a
database, and `AddressCodec` is the read-only facade that combines normalization, town
matching, lot number parsing, formatting, and positioning on that database.

## Components

| Component | Responsibility |
| --- | --- |
| [address_codec.py](address_codec.py) | `AddressCodec` facade: match, encode, resolve, decode, locate, find_nearest |
| [registry_importer.py](registry_importer.py) | `RegistryImporter`: imports the town master and position datasets into a writable database |
| [\_\_main\_\_.py](__main__.py) | `python -m address_codec_jp` entry point |
| [domain/](domain/) | Immutable domain models such as `AddressCode`, `Address`, and `Town` |
| [errors/](errors/) | Exception hierarchy rooted at `AddressCodecError` |
| [normalization/](normalization/) | Text normalization, kanji numerals, lot number parsing |
| [matching/](matching/) | Longest-prefix matching from text to a registered town |
| [storage/](storage/) | ABR CSV readers, the versioned SQLite `AddressDatabase`, and its town and position repositories |
| [positioning/](positioning/) | Representative point lookup with fallback, nearest address search, and datum transformation |
| [formatting/](formatting/) | Output format options and address rendering |
| [cli/](cli/) | Command line interface |

## Examples

```python
from pathlib import Path

from address_codec_jp import AddressCodec, RegistryImporter

with RegistryImporter.open("towns.sqlite3") as importer:
    importer.import_town_master(Path("mt_town_all.csv.zip"))

with AddressCodec.open("towns.sqlite3") as codec:
    print(codec.encode("千代田区丸の内1-2-3"))
```
