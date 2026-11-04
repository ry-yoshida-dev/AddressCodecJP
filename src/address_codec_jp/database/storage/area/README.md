# area

## Overview

Storage of area shapes. `AreaRepository` stores census small areas as
`CensusAreaRecord`s under their census codes, each with the towns it is matched to, and
the parcels of an `AreaBatch` as `AreaRecord`s, both with R*Tree indexes of their bounds,
and logs each imported file as an `AreaImport`. A municipality is made of all its census
areas, so names that match no town leave no hole in it.

## Components

| Component | Responsibility |
| --- | --- |
| [repository.py](repository.py) | `AreaRepository`: census areas and parcel shapes with R*Tree indexes of their bounds, and the log of the area files imported |
| [census_record.py](census_record.py) | `CensusAreaRecord`: census code, municipality, name, shape, and matched towns of a stored census area |
| [record.py](record.py) | `AreaRecord`: code, source, and shape of a parcel, or of a town looked up |
| [batch.py](batch.py) | `AreaBatch`: parcels of one registry map file matched to codes and the number of unmatched ones |
| [imported_file.py](imported_file.py) | `AreaImport`: source, municipality, file name, SHA-256, time, and stored and unmatched counts of one area import |
