# storage

## Overview

Loads the ABR town master and position datasets and persists them in one SQLite
database for lookup by code or municipality.

## Components

| Component | Responsibility |
| --- | --- |
| [abr_csv_file.py](abr_csv_file.py) | `AbrCsvFile`: reads rows of a registry CSV file or its ZIP archive |
| [abr_town_csv_reader.py](abr_town_csv_reader.py) | `AbrTownCsvReader`: reads `mt_town_all.csv` or its ZIP archive |
| [town_repository.py](town_repository.py) | `TownRepository`: SQLite store of towns; atomic replacement on import, read-only opening, and lookup of prefectures, municipalities, and towns |
| [import_summary.py](import_summary.py) | `ImportSummary`: numbers of registered and complemented towns |
| [abr_position_dataset.py](abr_position_dataset.py) | `AbrPositionDataset`: position-related datasets, identified by their CSV header |
| [abr_position_csv_reader.py](abr_position_csv_reader.py) | `AbrPositionCsvReader`: reads position extensions and the block, residence, and parcel number masters |
| [position_record.py](position_record.py) | `PositionRecord`: union of the records read from position datasets |
| [area_position.py](area_position.py) | `AreaPosition`: point of a prefecture or municipality |
| [town_position.py](town_position.py) | `TownPosition`: point and lot numbering system of a town |
| [lot_entry.py](lot_entry.py) | `LotEntry`: registry identifier of a block, residence, or parcel and its numbers |
| [lot_position.py](lot_position.py) | `LotPosition`: point of a block, residence, or parcel identifier |
| [position_repository.py](position_repository.py) | `PositionRepository`: SQLite store of points, joined from numbers and identifiers at lookup |
| [position_import_summary.py](position_import_summary.py) | `PositionImportSummary`: dataset and number of stored rows of an import |
