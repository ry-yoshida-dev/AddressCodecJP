# download

## Overview

Downloads Address Base Registry files from the registry download site
(`https://data.address-br.digital.go.jp`). A plan lists the nationwide town master and
prefecture and municipality points, the town, block, and residence files of chosen
prefectures, and the parcel files of chosen municipalities, in import order, using the
distribution scope of each `AbrDataset`. A lot plan lists the block, residence, and
parcel files of municipalities, and files the site does not distribute can be skipped.
Files are written atomically under their distributed names. Census boundaries
(e-Stat) and registry maps (G-Spatial Information Center) are downloaded per
municipality for area shapes.

Remote requests of a downloader start at least one second apart and send a
`User-Agent` naming the library, its version, and its repository, so that bulk
preparation does not burden the government sites. `file://` mirrors are read without
waiting.

## Components

| Component | Responsibility |
| --- | --- |
| [registry_downloader.py](registry_downloader.py) | `RegistryDownloader`: plans and downloads files, raising `RegistryDownloadError` on failure or truncation |
| [distributed_file.py](distributed_file.py) | `DistributedFile`: one distributed file of an `AbrDataset`, with its file name and URL path |
| [boundary_downloader.py](boundary_downloader.py) | `BoundaryDownloader`: census boundaries of a municipality from e-Stat and its latest registry maps found through every page of the G-Spatial CKAN catalog |
| [file_fetcher.py](file_fetcher.py) | `FileFetcher`: atomic download of one URL with spaced, identified remote requests, optionally treating a missing file as absent |

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
