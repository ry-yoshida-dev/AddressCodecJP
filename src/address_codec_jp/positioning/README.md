# positioning

## Overview

Finds the representative point of an address code from the imported registry points,
falling back to the nearest enclosing area that has one, and expresses it on the
requested datum. Also finds the address whose point is nearest to a coordinate.

## Components

| Component | Responsibility |
| --- | --- |
| [address_locator.py](address_locator.py) | `AddressLocator`: fallback from residence or block to town, oaza, municipality, and prefecture |
| [nearest_address_finder.py](nearest_address_finder.py) | `NearestAddressFinder`: nearest block, residence, parcel, or town point by growing square searches |
| [datum_converter.py](datum_converter.py) | `DatumConverter`: cached datum transformation of published points and coordinates |
