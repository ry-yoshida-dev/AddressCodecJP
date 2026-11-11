# matching

## Overview

Identifies the most specific registered area at the start of a normalized address,
matches groups of addresses that lie in one common area, and lists the areas that bear
a name.

## Components

| Component | Responsibility |
| --- | --- |
| [address_reader.py](address_reader.py) | `AddressReader`: normalizes text, matches single addresses and groups, searches names, and restores the remainder as written |
| [reading/](reading/README.md) | Reading of one address into its municipality, town, and lot numbers |
| [index/](index/README.md) | Indexes of the prefecture, municipality, oaza, and koaza names |
| [group_matcher.py](group_matcher.py) | `GroupMatcher`: finds the narrowest common area of a group of addresses and matches the ambiguous ones within it |
| [name_searcher.py](name_searcher.py) | `NameSearcher`: lists every prefecture, municipality, oaza, and koaza that bears a name |
| [town_source.py](town_source.py) | `TownSource`: protocol of the municipality, town, oaza, koaza name, and street direction lookups that matching needs, implemented by `TownRepository` |
