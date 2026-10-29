# positioning

## Overview

Finds the representative point of an address code from the imported registry points,
falling back to the nearest enclosing area that has one, and expresses it on the
requested datum.

## Components

| Component | Responsibility |
| --- | --- |
| [address_locator.py](address_locator.py) | `AddressLocator`: fallback from residence or block to town, oaza, municipality, and prefecture |
| [datum_converter.py](datum_converter.py) | `DatumConverter`: cached datum transformation of published points to `GeoCoordinate` |
