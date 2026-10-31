# geocoding

## Overview

Tests of representative points, nearest addresses, lot verification, and area shapes.
Fixtures come from [fixture_paths.py](../fixture_paths.py) and
[conftest.py](../conftest.py).

## Components

| Component | Responsibility |
| --- | --- |
| [test_locate.py](test_locate.py) | Representative points, fallback, lot systems, datums, and position imports |
| [test_nearest.py](test_nearest.py) | Nearest address search |
| [test_lot_verification.py](test_lot_verification.py) | Lot number verification against imported masters |
| [test_area.py](test_area.py) | Polygons, shape serialization, boundary and map readers, area import and lookup, boundary downloads and paged catalog searches, areas added by the cache, and the area commands |
