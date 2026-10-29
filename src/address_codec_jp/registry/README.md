# registry

## Overview

Reads the files of the Address Base Registry. A file is identified by its CSV header
(prefecture and municipality points, which share one header, by the code of the first
row), so files may be renamed, and both plain `.csv` files and `.zip` archives are
accepted.
The town master is read as `Town` records, and the position-related datasets as
`PositionRecord`s that `storage` persists.

## Components

| Component | Responsibility |
| --- | --- |
| [abr_csv_file.py](abr_csv_file.py) | `AbrCsvFile`: identifies the dataset of a registry CSV file or its ZIP archive and reads its rows, checking required columns and row lengths |
| [abr_csv_row.py](abr_csv_row.py) | `AbrCsvRow`: line number and required column values of one data row |
| [abr_dataset.py](abr_dataset.py) | `AbrDataset`: the downloadable and importable datasets, identified by their CSV header, with their distribution scope |
| [distribution_scope.py](distribution_scope.py) | `DistributionScope`: nationwide, per-prefecture, or per-municipality distribution |
| [abr_town_csv_reader.py](abr_town_csv_reader.py) | `AbrTownCsvReader`: reads `mt_town_all.csv`, skipping abolished rows and naming the row of malformed values |
| [abr_position_csv_reader.py](abr_position_csv_reader.py) | `AbrPositionCsvReader`: reads position extensions and the block, residence, and parcel number masters, turning abolished lots into removals |
| [position_record.py](position_record.py) | `PositionRecord`: union of the records read from position-related datasets |
| [area_position.py](area_position.py) | `AreaPosition`: point of a prefecture or municipality |
| [lot_entry.py](lot_entry.py) | `LotEntry`: registry identifier of a block, residence, or parcel and its numbers |
| [lot_position.py](lot_position.py) | `LotPosition`: point of a block, residence, or parcel identifier |
| [lot_removal.py](lot_removal.py) | `LotRemoval`: block, residence, or parcel marked abolished by a number master |
| [import_summary.py](import_summary.py) | `ImportSummary`: file, dataset, and numbers of stored, removed, and complemented rows of one import |

## Examples

```python
from pathlib import Path

from address_codec_jp.registry import AbrCsvFile, AbrTownCsvReader

path = Path("mt_town_all.csv.zip")
print(AbrCsvFile(path).detect_dataset())
for town in AbrTownCsvReader().read(path):
    print(town.lg_code, town.machiaza_id, town.oaza_name, town.chome_name)
```
