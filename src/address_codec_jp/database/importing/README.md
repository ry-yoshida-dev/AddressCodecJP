# importing

## Overview

Writes downloaded datasets into an `AddressDatabase`. Registry files are identified by
their header and imported atomically, the town master first. Area shapes carry names,
which are matched to address codes before they are stored.

## Components

| Component | Responsibility |
| --- | --- |
| [registry_importer.py](registry_importer.py) | `RegistryImporter`: identifies registry files by header and imports each atomically, the town master first |
| [area_importer.py](area_importer.py) | `AreaImporter`: matches census boundaries and registry map parcels to address codes and stores their shapes, the files of one municipality in one transaction |

## Examples

```python
from pathlib import Path

from address_codec_jp import RegistryImporter

with RegistryImporter.open("towns.sqlite3") as importer:
    importer.import_file(Path("mt_town_all.csv.zip"))
```
