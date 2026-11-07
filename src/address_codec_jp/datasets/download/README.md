# download

## Overview

Downloaders of Address Base Registry files, census boundaries, and registry maps. See
[docs/data-sources.md](../../../../docs/data-sources.md) for the sources and their terms.

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
