# domain

## Overview

Immutable value objects shared by all layers.

## Components

| Component | Responsibility |
| --- | --- |
| [address.py](address.py) | `Address`: registered prefecture, municipality, town, and lot numbers of a code, checked to contain each other; `for_town` builds one from a town |
| [address_area.py](address_area.py) | `AddressArea`: shape of an address and the area it stands for, with its sources |
| [address_code.py](address_code.py) | `AddressCode`: validated code with string parsing and rendering, its level, its enclosing areas (`parent`, `lineage`), and containment (`contains`) |
| [address_level.py](address_level.py) | `AddressLevel`: granularity from prefecture to residence |
| [address_location.py](address_location.py) | `AddressLocation`: representative point of an address and the area it stands for |
| [address_match.py](address_match.py) | `AddressMatch`: matched `Address`, remainder, postal code, and loosest name comparison of an input |
| [address_point.py](address_point.py) | `AddressPoint`: code of a town or lot and its published point |
| [area_shape.py](area_shape.py) | `AreaShape`: polygons of an area on JGD2011 with containment, bounds, serialization, and GeoJSON output |
| [area_source.py](area_source.py) | `AreaSource`: census boundaries or registry maps |
| [coordinate_bounds.py](coordinate_bounds.py) | `CoordinateBounds`: latitude and longitude range of a search area |
| [lot_number.py](lot_number.py) | `LotNumber`: block and residence numbers |
| [lot_system.py](lot_system.py) | `LotSystem`: residence indication or land parcel numbering |
| [match_tier.py](match_tier.py) | `MatchTier`: exact, prefix-insensitive, and variant-folded name comparison |
| [municipality.py](municipality.py) | `Municipality`: prefecture, county, city, and ward of a local government code and their readings |
| [nearest_address.py](nearest_address.py) | `NearestAddress`: address with the nearest point and its distance |
| [polygon.py](polygon.py) | `Polygon`: exterior and hole rings of longitude and latitude pairs, with point-in-polygon tests |
| [prefecture.py](prefecture.py) | `Prefecture`: validated two-digit prefecture code, name, and reading |
| [representative_point.py](representative_point.py) | `RepresentativePoint`: published longitude, latitude, and datum |
| [town.py](town.py) | `Town`: ABR town record within its `Municipality`, with readings, numbering systems, and postal codes |
| [town_position.py](town_position.py) | `TownPosition`: point and lot numbering system of a town |
