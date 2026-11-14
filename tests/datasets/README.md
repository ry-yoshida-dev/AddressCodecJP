# datasets

## Overview

Tests of downloading the registry datasets and of reading malformed files. Fixtures come from
[fixture_paths.py](../fixture_paths.py) and [conftest.py](../conftest.py).

## Components

| Component | Responsibility |
| --- | --- |
| [test_download.py](test_download.py) | Download plans, distributed files, atomic downloads from a `file://` mirror, failed and truncated downloads, and the `download` command |
| [test_malformed_files.py](test_malformed_files.py) | Broken archives and undecodable text in registry and shapefile data reported as format errors, and the exit status of the `import` command for them |
