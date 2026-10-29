# storage

## Overview

Loads the ABR town master and persists towns in SQLite for lookup by code or municipality.

## Components

| Component | Responsibility |
| --- | --- |
| [abr_town_csv_reader.py](abr_town_csv_reader.py) | `AbrTownCsvReader`: reads `mt_town_all.csv` or its ZIP archive |
| [town_repository.py](town_repository.py) | `TownRepository`: SQLite store of towns; atomic replacement on import, read-only opening, and lookup of prefectures, municipalities, and towns |
| [import_summary.py](import_summary.py) | `ImportSummary`: numbers of registered and complemented towns |
