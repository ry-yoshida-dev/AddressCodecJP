# domain

## Overview

Immutable value objects shared by all layers.

## Components

| Component | Responsibility |
| --- | --- |
| [address_code.py](address_code.py) | `AddressCode`: validated prefecture, municipality, or town code with string parsing and rendering |
| [address_level.py](address_level.py) | `AddressLevel`: prefecture, municipality, or town granularity |
| [address_location.py](address_location.py) | `AddressLocation`: representative point of an address and the area it stands for |
| [address_match.py](address_match.py) | `AddressMatch`: matched prefecture, municipality, town, lot numbers, and remainder of an input |
| [lot_number.py](lot_number.py) | `LotNumber`: block and residence numbers |
| [lot_system.py](lot_system.py) | `LotSystem`: residence indication or land parcel numbering |
| [municipality.py](municipality.py) | `Municipality`: prefecture, county, city, and ward of a local government code |
| [position_level.py](position_level.py) | `PositionLevel`: granularity of a representative point, from prefecture to residence |
| [prefecture.py](prefecture.py) | `Prefecture`: two-digit prefecture code and name |
| [representative_point.py](representative_point.py) | `RepresentativePoint`: published longitude, latitude, and datum |
| [town.py](town.py) | `Town`: ABR town record |
