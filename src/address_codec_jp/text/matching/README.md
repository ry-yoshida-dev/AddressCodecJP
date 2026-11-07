# matching

## Overview

Identifies the most specific registered area at the start of a normalized address,
matches groups of addresses that lie in one common area, and lists the areas that bear
a name.

## Components

| Component | Responsibility |
| --- | --- |
| [address_reader.py](address_reader.py) | `AddressReader`: normalizes text, matches single addresses and groups, searches names, and restores the remainder as written |
| [area_matcher.py](area_matcher.py) | `AreaMatcher`: builds, ranks, and checks readings of an address and returns an `AddressMatch`, or raises `AmbiguousAddressError` with the candidate codes; `find` returns `None` instead of raising for an unmatched or ambiguous address, and `interpret` returns the failure |
| [street_direction_reader.py](street_direction_reader.py) | `StreetDirectionReader`: finds where a Kyoto street direction ends, matches it against registered ones with notation variants folded, and ranks oaza of one name by the streets an unregistered direction names |
| [group_matcher.py](group_matcher.py) | `GroupMatcher`: finds the narrowest common area of a group of addresses and matches the ambiguous ones within it |
| [name_searcher.py](name_searcher.py) | `NameSearcher`: lists every prefecture, municipality, oaza, and koaza that bears a name |
| [municipality_name_index.py](municipality_name_index.py) | `MunicipalityNameIndex`: prefecture and municipality names with their abbreviations, built on first use; one instance is shared by `AreaMatcher` and `NameSearcher` |
| [town_name_index.py](town_name_index.py) | `TownNameIndex`: oaza names nationwide and per municipality, koaza names per oaza reading, the municipalities with street directions, and the street directions and oaza-level towns of a municipality, each built on first use |
| [name_index.py](name_index.py) | `NameIndex`: tiered prefix index of oaza or koaza names |
| [candidate_set.py](candidate_set.py) | `CandidateSet`: towns compatible with a partial reading and the loosest `MatchTier` used |
| [town_interpretation.py](town_interpretation.py) | `TownInterpretation`: a complete reading and its ranking key |
| [municipality_match.py](municipality_match.py) | `MunicipalityMatch`: municipalities matching the leading name and remaining text |
| [town_source.py](town_source.py) | `TownSource`: protocol of the municipality, town, oaza, koaza name, and street direction lookups that matching needs, implemented by `TownRepository` |
