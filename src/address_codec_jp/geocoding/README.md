# geocoding

## Overview

Finds the representative point of an address code from the imported registry points,
falling back to the nearest enclosing area that has one, and expresses it on the
requested datum. Also finds the address whose point is nearest to a coordinate, the
shape of an address code, and the shapes that contain a coordinate.

## Components

| Component | Responsibility |
| --- | --- |
| [geocoder.py](geocoder.py) | `Geocoder`: adds the lots or shapes a lookup may need from a `DatasetSupplier`, then locates codes, finds nearest addresses and shapes, and verifies lot numbers; lot numbers of a Kyoto street direction are looked up on its oaza |
| [address_locator.py](address_locator.py) | `AddressLocator`: fallback along `AddressCode.lineage` from residence or block to town, oaza, municipality, and prefecture |
| [nearest_address_finder.py](nearest_address_finder.py) | `NearestAddressFinder`: nearest block, residence, parcel, or town point by growing square searches |
| [area_finder.py](area_finder.py) | `AreaFinder`: shape of a code with fallback to its town, oaza, or municipality, and the shapes containing a coordinate |
| [datum_converter.py](datum_converter.py) | `DatumConverter`: cached datum transformation of published points and coordinates |
| [dataset_supplier.py](dataset_supplier.py) | `DatasetSupplier`: protocol of the per-municipality dataset provisioning that geocoding needs, implemented by `DatabaseCache` |
| [position_source.py](position_source.py) | `PositionSource`: protocol of the point lookups that locating needs, implemented by `PositionRepository` |
