# address

## Overview

Results of looking up one address: how its text matched, its representative point, and
its shape.

## Components

| Component | Responsibility |
| --- | --- |
| [match.py](match.py) | `AddressMatch`: matched `Address`, remainder, postal code, and loosest name comparison of an input |
| [location.py](location.py) | `AddressLocation`: representative point of an address and the area it stands for |
| [area.py](area.py) | `AddressArea`: shape of an address and the area it stands for, with its sources |
