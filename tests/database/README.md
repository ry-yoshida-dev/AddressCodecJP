# database

## Overview

Tests of the SQLite storage, the importers, the lookup of registered areas, and the
default database cache. Fixtures come from [fixture_paths.py](../fixture_paths.py) and
[conftest.py](../conftest.py).

## Components

| Component | Responsibility |
| --- | --- |
| [test_storage.py](test_storage.py) | Town master import, numbering systems, abolished rows, orphaned positions, read-only opening, and database identification |
| [test_children.py](test_children.py) | Areas directly under prefectures, municipalities, and oaza, and the `children` command |
| [test_postal_lookup.py](test_postal_lookup.py) | Postal code parsing, towns by postal code, and the `postal` command |
| [test_import_files.py](test_import_files.py) | Dataset detection, ordering and deduplication of `import_files`, transaction rollback, and the `import` command |
| [test_import_log.py](test_import_log.py) | Import log of datasets, digests, and the `info` command |
| [test_database_cache.py](test_database_cache.py) | Building, reusing, and failed builds of the default database, lots added on demand, preparation, offline use, expiry and failed expiry refreshes, unpublished files not requested again, concurrent writers, logging, description, refresh, clearing, removal of obsolete files while keeping newer schema versions, and its use by `AddressCodec.open` and the `cache` command |
