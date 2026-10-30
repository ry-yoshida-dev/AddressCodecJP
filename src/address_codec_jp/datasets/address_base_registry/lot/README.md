# lot

## Overview

Records of blocks, residences, and land parcels read from the position datasets and
number masters of the registry.

## Components

| Component | Responsibility |
| --- | --- |
| [entry.py](entry.py) | `LotEntry`: registry identifier of a block, residence, or parcel and its numbers |
| [position.py](position.py) | `LotPosition`: point of a block, residence, or parcel identifier |
| [removal.py](removal.py) | `LotRemoval`: block, residence, or parcel marked abolished by a number master |
