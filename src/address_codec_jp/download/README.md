# download

## Overview

Downloads Address Base Registry files from the registry download site
(`https://data.address-br.digital.go.jp`). A plan lists the nationwide town master and
prefecture and municipality points, the town, block, and residence files of chosen
prefectures, and the parcel files of chosen municipalities, in import order, using the
distribution scope of each `AbrDataset`. Files are written atomically under their
distributed names.

## Components

| Component | Responsibility |
| --- | --- |
| [registry_downloader.py](registry_downloader.py) | `RegistryDownloader`: plans and downloads files, raising `RegistryDownloadError` on failure or truncation |
| [distributed_file.py](distributed_file.py) | `DistributedFile`: one distributed file of an `AbrDataset`, with its file name and URL path |

## Examples

```python
from pathlib import Path

from address_codec_jp import RegistryDownloader, RegistryImporter

downloader = RegistryDownloader()
paths = [
    downloader.download(target, Path("data"), is_existing_kept=True)
    for target in downloader.plan(prefecture_codes=["31"], municipality_codes=["312011"])
]
with RegistryImporter.open("towns.sqlite3") as importer:
    importer.import_files(paths)
```
