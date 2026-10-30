# geometry

## Overview

Points and polygons: published representative points, the points of towns and lots, and
area shapes on JGD2011. GeoJSON output follows RFC 7946: exterior rings run
counterclockwise and holes clockwise, whatever the orientation of the source data.

## Components

| Component | Responsibility |
| --- | --- |
| [polygon.py](polygon.py) | `Polygon`: exterior and hole rings of longitude and latitude pairs, with point-in-polygon tests |
| [coordinate_bounds.py](coordinate_bounds.py) | `CoordinateBounds`: latitude and longitude range of a search area |
| [area_shape.py](area_shape.py) | `AreaShape`: polygons of an area on JGD2011 with containment, bounds, serialization, and GeoJSON output |
| [representative_point.py](representative_point.py) | `RepresentativePoint`: published longitude, latitude, and datum |
| [address_point.py](address_point.py) | `AddressPoint`: code of a town or lot and its published point |
| [town_position.py](town_position.py) | `TownPosition`: point and lot numbering system of a town |
