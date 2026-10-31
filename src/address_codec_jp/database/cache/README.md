# cache

## Overview

`DatabaseCache` keeps the default address database in the user cache directory. It is
built on first use with the nationwide town master and town points, and the points and
area shapes of each municipality are added when a lookup needs them or ahead of time with
`prepare`. Writes are serialized across processes by a lock file. Registry files and
area datasets that the sites do not publish are remembered, so that they are not
requested again after every addition. Databases of older schema versions are removed
when a new one is built; those of newer versions are kept for the library that uses them.
Only the cache's own databases and marked working directories are ever deleted, so the
cache directory may hold other files.
Progress is logged at INFO level to the `address_codec_jp.database.cache` loggers.

The registry maps of a municipality, one archive per registry office, are imported
together, so a failed archive leaves the municipality to be added again in full. The
import ledger is read again whenever the database file changes. A codec opens its
database with `DatabaseCache.open_database`; once that file has been replaced or removed,
such as by `refresh` or `clear` in any process, additions for the codec raise
`DatabaseReplacedError` (a `DatasetNotImportedError`) instead of going to a file the
codec does not read, and the codec has to be opened again. Without downloads, the codec
keeps reading the file it opened. `max_age` requires downloads, and a refresh on first
use that fails to download, read, or write keeps the current database with a warning.

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
