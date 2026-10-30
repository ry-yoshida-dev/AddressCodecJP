# results

## Overview

Values returned by `AddressCodec`: the match of an input text, the location, shape, and
nearest address of a code or coordinate.

## Components

| Component | Responsibility |
| --- | --- |
| [address/](address/) | Match, location, and shape of an address |
| [match_tier.py](match_tier.py) | `MatchTier`: exact, prefix-insensitive, and variant-folded name comparison |
| [nearest_address.py](nearest_address.py) | `NearestAddress`: address with the nearest point and its distance |
| [area_source.py](area_source.py) | `AreaSource`: census boundaries or registry maps |
