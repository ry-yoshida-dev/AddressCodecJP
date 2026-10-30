# storage

## Overview

Persists imported registry datasets in one versioned SQLite database for lookup by
code, municipality, postal code, or coordinate. Repositories never commit on their own;
`AddressDatabase.transaction` groups their writes, so that each import is stored
completely or not at all.

## Components

| Component | Responsibility |
| --- | --- |
| [address_database.py](address_database.py) | `AddressDatabase`: owns the SQLite connection, opens read-only or writable, groups writes in transactions, and rejects files of another application or schema version |
| [town_repository.py](town_repository.py) | `TownRepository`: municipalities, towns, postal codes, and numbering systems; replacement on import and lookup of prefectures, municipalities, and towns, of the areas directly under them, and of towns by oaza or koaza name |
| [town_replacement.py](town_replacement.py) | `TownReplacement`: numbers of stored and complemented towns of a replacement |
| [lot_system_column.py](lot_system_column.py) | `LotSystemColumn`: compact integer stored for each `LotSystem` |
| [position_repository.py](position_repository.py) | `PositionRepository`: points, joined from numbers and identifiers at lookup; lot existence checks, bounding-box queries, and removal of orphaned rows |
| [position_changes.py](position_changes.py) | `PositionChanges`: numbers of stored records and removed lots |
| [import_log_repository.py](import_log_repository.py) | `ImportLogRepository`: log of the imported registry files |
| [area/](area/) | Area shapes, their R*Tree index, and the log of imported area files |
| [dataset_import.py](dataset_import.py) | `DatasetImport`: dataset, file name, SHA-256, time, and row count of one import |
