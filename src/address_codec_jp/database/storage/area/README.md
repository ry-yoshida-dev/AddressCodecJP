# area

## Overview

Storage of census areas and parcel shapes with a spatial index of their bounds, and the
log of imported area files.

## Components

| Component | Responsibility |
| --- | --- |
| [repository.py](repository.py) | `AreaRepository`: census areas and parcel shapes with R*Tree indexes of their bounds, and the log of the area files imported |
| [census_record.py](census_record.py) | `CensusAreaRecord`: census code, municipality, name, shape, and matched towns of a stored census area |
| [record.py](record.py) | `AreaRecord`: code, source, and shape of a parcel, or of a town looked up |
| [batch.py](batch.py) | `AreaBatch`: parcels of one registry map file matched to codes and the number of unmatched ones |
| [imported_file.py](imported_file.py) | `AreaImport`: source, municipality, file name, SHA-256, time, and stored and unmatched counts of one area import |
