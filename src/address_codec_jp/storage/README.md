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
| [town_repository.py](town_repository.py) | `TownRepository`: municipalities, towns, postal codes, and numbering systems; replacement on import and lookup of prefectures, municipalities, and towns |
| [town_replacement.py](town_replacement.py) | `TownReplacement`: numbers of stored and complemented towns of a replacement |
| [position_repository.py](position_repository.py) | `PositionRepository`: points, joined from numbers and identifiers at lookup; lot existence checks, bounding-box queries, and removal of orphaned rows |
| [position_changes.py](position_changes.py) | `PositionChanges`: numbers of stored records and removed lots |
| [import_log_repository.py](import_log_repository.py) | `ImportLogRepository`: log of the imported registry files |
| [area_repository.py](area_repository.py) | `AreaRepository`: area shapes with an R*Tree index of their bounds, and the log of the area files imported |
| [area_record.py](area_record.py) | `AreaRecord`: code, source, and shape of a stored area |
| [area_batch.py](area_batch.py) | `AreaBatch`: shapes of one area file matched to codes and the number of unmatched ones |
| [area_import.py](area_import.py) | `AreaImport`: source, municipality, file name, SHA-256, time, and stored and unmatched counts of one area import |
| [dataset_import.py](dataset_import.py) | `DatasetImport`: dataset, file name, SHA-256, time, and row count of one import |
