# importing

## Overview

Writes downloaded registry files and area shapes into an `AddressDatabase`.

## Components

| Component | Responsibility |
| --- | --- |
| [registry_importer.py](registry_importer.py) | `RegistryImporter`: identifies registry files by header and imports each atomically, the town master first |
| [area_importer.py](area_importer.py) | `AreaImporter`: stores every census area with the towns its name matches, and registry map parcels under their address codes, the files of one municipality in one transaction |
| [census_area_matcher.py](census_area_matcher.py) | `CensusAreaMatcher`: matches census area names to towns, also when the census leaves out a leading part that several oaza share (`三大寺` for `水口町三大寺`) or a trailing `町` |

## Examples

```python
from pathlib import Path

from address_codec_jp import RegistryImporter

with RegistryImporter.open("towns.sqlite3") as importer:
    importer.import_file(Path("mt_town_all.csv.zip"))
```
