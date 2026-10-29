# boundary

## Overview

Reads the area shapes published outside the Address Base Registry: the town
boundaries of the 2020 census (e-Stat, shapefile on JGD2011) and the land parcel maps
of the registry offices (map XML on the plane rectangular coordinate system). Sheets on
an arbitrary local coordinate system cannot be placed and are skipped; the others are
projected to JGD2011. Shapes carry names, which `AreaImporter` matches to address codes.

## Components

| Component | Responsibility |
| --- | --- |
| [shapefile_reader.py](shapefile_reader.py) | `ShapefileReader`: polygons and attributes of a zipped shapefile, with holes assigned to their exteriors |
| [shapefile_record.py](shapefile_record.py) | `ShapefileRecord`: attributes and polygons of one feature |
| [census_boundary_reader.py](census_boundary_reader.py) | `CensusBoundaryReader`: named land areas of the census, with the polygons of one census code combined |
| [census_area.py](census_area.py) | `CensusArea`: census code, address text, and shape of one area |
| [registry_map_reader.py](registry_map_reader.py) | `RegistryMapReader`: parcels of nested map archives, chaining curves into rings and projecting them |
| [registry_map_parcel.py](registry_map_parcel.py) | `RegistryMapParcel`: municipality, oaza, chome, parcel number, and shape of one parcel |

## Examples

```python
from pathlib import Path

from address_codec_jp.boundary import CensusBoundaryReader

for area in CensusBoundaryReader().read(Path("census_boundary_131016.zip"))[:3]:
    print(area.address, area.shape.bounds)
```
