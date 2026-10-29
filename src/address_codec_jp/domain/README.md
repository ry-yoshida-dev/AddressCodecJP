# domain

## Overview

Immutable value objects shared by all layers.

## Components

| Component | Responsibility |
| --- | --- |
| [address_code.py](address_code.py) | `AddressCode`: validated prefecture, municipality, or town code with string parsing and rendering |
| [address_level.py](address_level.py) | `AddressLevel`: prefecture, municipality, or town granularity |
| [address_match.py](address_match.py) | `AddressMatch`: matched prefecture, municipality, town, lot numbers, and remainder of an input |
| [lot_number.py](lot_number.py) | `LotNumber`: block and residence numbers |
| [municipality.py](municipality.py) | `Municipality`: prefecture, county, city, and ward of a local government code |
| [prefecture.py](prefecture.py) | `Prefecture`: two-digit prefecture code and name |
| [town.py](town.py) | `Town`: ABR town record |
