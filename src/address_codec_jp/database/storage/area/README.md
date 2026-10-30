# area

## Overview

Storage of area shapes. `AreaRepository` stores the shapes of an `AreaBatch` as
`AreaRecord`s with an R*Tree index of their bounds, and logs each imported file as an
`AreaImport`.

## Components

| Component | Responsibility |
| --- | --- |
| [repository.py](repository.py) | `AreaRepository`: area shapes with an R*Tree index of their bounds, and the log of the area files imported |
| [record.py](record.py) | `AreaRecord`: code, source, and shape of a stored area |
| [batch.py](batch.py) | `AreaBatch`: shapes of one area file matched to codes and the number of unmatched ones |
| [imported_file.py](imported_file.py) | `AreaImport`: source, municipality, file name, SHA-256, time, and stored and unmatched counts of one area import |
