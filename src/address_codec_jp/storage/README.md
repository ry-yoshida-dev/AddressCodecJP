# storage

## Overview

Loads the ABR town master and position datasets and persists them in one SQLite
database for lookup by code or municipality.

## Components

| Component | Responsibility |
| --- | --- |
| [abr_csv_file.py](abr_csv_file.py) | `AbrCsvFile`: reads rows of a registry CSV file or its ZIP archive |
| [abr_town_csv_reader.py](abr_town_csv_reader.py) | `AbrTownCsvReader`: reads `mt_town_all.csv` or its ZIP archive, skipping abolished rows |
| [town_repository.py](town_repository.py) | `TownRepository`: SQLite store of municipalities, towns, and postal codes; atomic replacement on import, read-only opening with schema check, and lookup of prefectures, municipalities, and towns |
| [town_replacement.py](town_replacement.py) | `TownReplacement`: numbers of stored and complemented towns of a replacement |
| [import_summary.py](import_summary.py) | `ImportSummary`: numbers of registered and complemented towns and removed position rows of a town master import |
| [abr_position_dataset.py](abr_position_dataset.py) | `AbrPositionDataset`: position-related datasets, identified by their CSV header |
| [abr_position_csv_reader.py](abr_position_csv_reader.py) | `AbrPositionCsvReader`: reads position extensions and the block, residence, and parcel number masters, turning abolished lots into removals |
| [position_record.py](position_record.py) | `PositionRecord`: union of the records read from position datasets |
| [area_position.py](area_position.py) | `AreaPosition`: point of a prefecture or municipality |
| [town_position.py](town_position.py) | `TownPosition`: point and lot numbering system of a town |
| [lot_entry.py](lot_entry.py) | `LotEntry`: registry identifier of a block, residence, or parcel and its numbers |
| [lot_position.py](lot_position.py) | `LotPosition`: point of a block, residence, or parcel identifier |
| [lot_removal.py](lot_removal.py) | `LotRemoval`: block, residence, or parcel marked abolished by a number master |
| [position_changes.py](position_changes.py) | `PositionChanges`: numbers of stored records and removed lots |
| [position_repository.py](position_repository.py) | `PositionRepository`: SQLite store of points, joined from numbers and identifiers at lookup; lot existence checks, bounding-box queries, and removal of orphaned rows |
| [position_import_summary.py](position_import_summary.py) | `PositionImportSummary`: dataset and numbers of stored rows and removed lots of an import |
