# address

## Overview

Registered address units: the address code and its level, the prefecture, municipality,
and town records, lot numbers, and the full `Address` they make up.

## Components

| Component | Responsibility |
| --- | --- |
| [address.py](address.py) | `Address`: registered prefecture, municipality, town, and lot numbers of a code, checked to contain each other; `for_town` builds one from a town |
| [code.py](code.py) | `AddressCode`: validated code with string parsing and rendering, its level, its enclosing areas (`parent`, `lineage`), and containment (`contains`) |
| [level.py](level.py) | `AddressLevel`: granularity from prefecture to residence |
| [prefecture.py](prefecture.py) | `Prefecture`: validated two-digit prefecture code, name, and reading |
| [municipality.py](municipality.py) | `Municipality`: prefecture, county, city, and ward of a local government code and their readings |
| [town.py](town.py) | `Town`: ABR town record within its `Municipality`, with readings, numbering systems, and postal codes |
| [lot_number.py](lot_number.py) | `LotNumber`: block and residence numbers |
| [lot_system.py](lot_system.py) | `LotSystem`: residence indication or land parcel numbering |
