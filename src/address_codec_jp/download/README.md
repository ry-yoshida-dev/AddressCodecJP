# download

## Overview

Downloads Address Base Registry files from the registry download site
(`https://data.address-br.digital.go.jp`). A plan lists the nationwide town master and
prefecture and municipality points, the town, block, and residence files of chosen
prefectures, and the parcel files of chosen municipalities, in import order. Files are
written atomically under their distributed names.

## Components

| Component | Responsibility |
| --- | --- |
| [registry_downloader.py](registry_downloader.py) | `RegistryDownloader`: plans and downloads files, raising `RegistryDownloadError` on failure |
| [download_target.py](download_target.py) | `DownloadTarget`: one distributed file, with its file name and URL path |
| [registry_file.py](registry_file.py) | `RegistryFile`: downloadable datasets and their distribution scope |
| [distribution_scope.py](distribution_scope.py) | `DistributionScope`: nationwide, per-prefecture, or per-municipality distribution |

## Examples

```python
from pathlib import Path

from address_codec_jp import RegistryDownloader, RegistryImporter

downloader = RegistryDownloader()
with RegistryImporter.open("towns.sqlite3") as importer:
    for target in downloader.plan(prefecture_codes=["31"], municipality_codes=["312011"]):
        path = downloader.download(target, Path("data"), is_existing_kept=True)
        if target.registry_file.name == "TOWN":
            importer.import_town_master(path)
        else:
            importer.import_positions(path)
```
