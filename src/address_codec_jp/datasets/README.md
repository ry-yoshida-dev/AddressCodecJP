# datasets

## Overview

External datasets the database is built from: downloading them and reading their file
formats into records.

## Components

| Component | Responsibility |
| --- | --- |
| [address_base_registry/](address_base_registry/) | Readers of the Address Base Registry (ABR) CSV files, dataset detection, and the records they yield |
| [boundaries/](boundaries/) | Readers of census town boundary shapefiles and registry office map XML |
| [download/](download/) | Downloaders of registry files, census boundaries, and registry maps |
