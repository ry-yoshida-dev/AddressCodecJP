# results

## Overview

Values returned by `AddressCodec`: the match of an input text, the location, shape, and
nearest address of a code or coordinate.

## Components

| Component | Responsibility |
| --- | --- |
| [address_match.py](address_match.py) | `AddressMatch`: matched `Address`, remainder, postal code, and loosest name comparison of an input |
| [match_tier.py](match_tier.py) | `MatchTier`: exact, prefix-insensitive, and variant-folded name comparison |
| [address_location.py](address_location.py) | `AddressLocation`: representative point of an address and the area it stands for |
| [nearest_address.py](nearest_address.py) | `NearestAddress`: address with the nearest point and its distance |
| [address_area.py](address_area.py) | `AddressArea`: shape of an address and the area it stands for, with its sources |
| [area_source.py](area_source.py) | `AreaSource`: census boundaries or registry maps |
