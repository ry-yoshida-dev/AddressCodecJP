# address_codec_jp

## Overview

Public package of AddressCodecJP. `RegistryImporter` imports registry datasets into a
database, and `AddressCodec` is the read-only facade that combines normalization, town
matching, lot number parsing, formatting, and positioning on that database.
`DatabaseCache` builds a nationwide town-level database in the user cache directory on
first use, which `AddressCodec.open()` opens when no path is given.

## Components

| Component | Responsibility |
| --- | --- |
| [address_codec.py](address_codec.py) | `AddressCodec` facade: match, encode, resolve, decode, list_by_postal_code, locate, find_nearest |
| [database_cache.py](database_cache.py) | `DatabaseCache`: downloads and builds the default town-level database once per schema version |
| [registry_importer.py](registry_importer.py) | `RegistryImporter`: identifies registry files by header and imports each atomically, the town master first |
| [\_\_main\_\_.py](__main__.py) | `python -m address_codec_jp` entry point |
| [domain/](domain/) | Immutable domain models such as `AddressCode`, `Address`, and `Town` |
| [download/](download/) | Downloader of registry files from the ABR download site |
| [errors/](errors/) | Exception hierarchy rooted at `AddressCodecError` |
| [normalization/](normalization/) | Text normalization, kanji numerals, lot number parsing |
| [matching/](matching/) | Longest-prefix matching from text to a registered town |
| [registry/](registry/) | ABR CSV readers, dataset detection, and the records read from registry files |
| [storage/](storage/) | Versioned SQLite `AddressDatabase`, its transactions, and its town, position, and import log repositories |
| [positioning/](positioning/) | Representative point lookup with fallback, nearest address search, and datum transformation |
| [formatting/](formatting/) | Output format options and address rendering |
| [cli/](cli/) | Command line interface |

## Examples

```python
from pathlib import Path

from address_codec_jp import AddressCodec, RegistryImporter

with AddressCodec.open() as codec:
    print(codec.encode("千代田区丸の内1-2-3"))

with RegistryImporter.open("towns.sqlite3") as importer:
    importer.import_file(Path("mt_town_all.csv.zip"))

with AddressCodec.open("towns.sqlite3") as codec:
    print(codec.encode("千代田区丸の内1-2-3"))
```
