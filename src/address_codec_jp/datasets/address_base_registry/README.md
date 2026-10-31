# address_base_registry

## Overview

Reads Address Base Registry files, plain `.csv` or `.zip`. The dataset is identified by
the CSV header, so files may be renamed. The town master is read as `Town` records, and
the position-related datasets as `PositionRecord`s that `storage` persists.

## Components

| Component | Responsibility |
| --- | --- |
| [csv_file.py](csv_file.py) | `AbrCsvFile`: identifies the dataset of a registry CSV file or its ZIP archive and reads its rows, checking required columns and row lengths |
| [csv_row.py](csv_row.py) | `AbrCsvRow`: line number and required column values of one data row |
| [dataset.py](dataset.py) | `AbrDataset`: the downloadable and importable datasets, identified by their CSV header, with their distribution scope |
| [distribution_scope.py](distribution_scope.py) | `DistributionScope`: nationwide, per-prefecture, or per-municipality distribution |
| [town_csv_reader.py](town_csv_reader.py) | `AbrTownCsvReader`: reads `mt_town_all.csv`, skipping abolished rows, marking Kyoto street directions by `koaza_aka_code`, and naming the row of malformed values |
| [position_csv_reader.py](position_csv_reader.py) | `AbrPositionCsvReader`: reads position extensions and the block, residence, and parcel number masters, turning abolished lots into removals |
| [position_record.py](position_record.py) | `PositionRecord`: union of the records read from position-related datasets |
| [area_position.py](area_position.py) | `AreaPosition`: point of a prefecture or municipality |
| [lot/](lot/) | Blocks, residences, and parcels read from the registry: identifiers, points, and removals |
| [import_summary.py](import_summary.py) | `ImportSummary`: file, dataset, and numbers of stored, removed, and complemented rows of one import |

## Examples

```python
from pathlib import Path

from address_codec_jp.datasets.address_base_registry import AbrCsvFile, AbrTownCsvReader

path = Path("mt_town_all.csv.zip")
print(AbrCsvFile(path).detect_dataset())
for town in AbrTownCsvReader().read(path):
    print(town.lg_code, town.machiaza_id, town.oaza_name, town.chome_name)
```
