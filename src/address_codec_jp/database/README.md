# database

## Overview

The SQLite address database: its schema and repositories, the importers that fill it
from the [datasets](../datasets/), and the default database kept in the user cache
directory.

## Components

| Component | Responsibility |
| --- | --- |
| [storage/](storage/) | Versioned SQLite `AddressDatabase`, its transactions, and its town, position, area, and import log repositories |
| [importing/](importing/) | `RegistryImporter` and `AreaImporter`, which write registry files and area shapes into a database |
| [cache/](cache/) | `DatabaseCache`: the default database, built on first use and extended per municipality |
