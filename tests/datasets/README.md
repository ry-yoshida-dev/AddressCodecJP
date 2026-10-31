# datasets

## Overview

Tests of downloading the registry datasets. Fixtures come from
[fixture_paths.py](../fixture_paths.py) and [conftest.py](../conftest.py).

## Components

| Component | Responsibility |
| --- | --- |
| [test_download.py](test_download.py) | Download plans, distributed files, atomic downloads from a `file://` mirror, failed and truncated downloads, and the `download` command |
