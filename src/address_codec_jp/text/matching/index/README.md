# index

## Overview

Indexes of the registry names that matching looks the leading text of an address up in,
each built on first use.

## Components

| Component | Responsibility |
| --- | --- |
| [municipality_name_index.py](municipality_name_index.py) | `MunicipalityNameIndex`: prefecture and municipality names with their abbreviations; one instance is shared by `AreaMatcher` and `NameSearcher` |
| [town_name_index.py](town_name_index.py) | `TownNameIndex`: oaza names nationwide and per municipality, koaza names per oaza reading, the municipalities with street directions, and the street directions and oaza-level towns of a municipality |
| [name_index.py](name_index.py) | `NameIndex`: tiered prefix index of oaza or koaza names |
| [candidate_set.py](candidate_set.py) | `CandidateSet`: towns compatible with a partial reading and the loosest `MatchTier` used |
