# address_codec_jp

## Overview

Public package of AddressCodecJP. `AddressCodec` is the read-only facade that
normalizes, matches, encodes, decodes, and geocodes addresses on an address database;
`RegistryImporter` imports registry datasets into a database, and `DatabaseCache`
provides the default database, built on first use.

## Components

| Component | Responsibility |
| --- | --- |
| [address_codec.py](address_codec.py) | `AddressCodec` facade: match, match_group, encode, resolve, decode, list_children, list_by_postal_code, list_by_name, locate, find_nearest, find_area, find_areas_at; delegates to `AddressReader`, `AddressDirectory`, and `Geocoder` |
| [\_\_main\_\_.py](__main__.py) | `python -m address_codec_jp` entry point |
| [address/](address/) | Address codes and registered units: prefecture, municipality, town, and lot numbers |
| [geometry/](geometry/) | Representative points and polygons |
| [results/](results/) | Values returned by `AddressCodec`: matches, locations, nearest addresses, and areas |
| [errors/](errors/) | Exception hierarchy rooted at `AddressCodecError` |
| [text/](text/) | Normalization, town matching, and formatting of address text |
| [geocoding/](geocoding/) | Address to point and shape with fallback, coordinate to nearest address and containing areas, and datum transformation |
| [datasets/](datasets/) | Downloading and reading the Address Base Registry, census boundaries, and registry maps |
| [database/](database/) | SQLite storage, the importers that fill it, and the default database in the user cache directory |
| [frontends/](frontends/) | Command line, optional web API, and their shared JSON serialization |

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
