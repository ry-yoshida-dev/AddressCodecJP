# cache

## Overview

`DatabaseCache` keeps the default address database in the user cache directory, built
on first use and extended per municipality when a lookup needs it or ahead of time with
`prepare`, optionally showing download and import progress bars. See
[docs/cache.md](../../../../docs/cache.md) for its location and environment variables.

## Components

| Component | Responsibility |
| --- | --- |
| [database_cache.py](database_cache.py) | `DatabaseCache`: decides when the database is built, extended, prepared, refreshed, described, and cleared, optionally without downloads on use or with a maximum age |
| [loader.py](loader.py) | `CacheLoader`: downloads and imports the town master, registry files, and area datasets under the directory lock |
| [directory.py](directory.py) | `CacheDirectory`: database path, lock, working directories, and obsolete files of the cache directory |
| [import_ledger.py](import_ledger.py) | `ImportLedger`: registry files and area datasets that are imported or known to be unpublished |
| [area_target.py](area_target.py) | `AreaTarget`: one area dataset of one municipality to add |
| [file_signature.py](file_signature.py) | `DatabaseFileSignature`: device, inode, modification time, and size of the database file |
| [opened_database.py](opened_database.py) | `OpenedDatabase`: database a cache opened for a codec and the file it was opened on |
| [status.py](status.py) | `CacheStatus`: path, size, build time, municipalities added, and obsolete files of the cache |

## Examples

```python
from address_codec_jp import AddressCodec, DatabaseCache

DatabaseCache.default().prepare(prefecture_codes=["13"])
with AddressCodec.open(cache=DatabaseCache.default(is_download_allowed=False)) as codec:
    print(codec.locate("千代田区丸の内1-9-1"))
```
