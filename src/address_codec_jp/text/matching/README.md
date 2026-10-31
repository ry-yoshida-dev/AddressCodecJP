# matching

## Overview

Identifies the most specific registered area at the start of a normalized address.
The municipality is found by longest prefix, and a name shared by several
municipalities is resolved by the town name. A ward written without its city, or an
address that starts with a town name, is resolved by trying every municipality with
such a ward or oaza. Every reading of oaza, chome, koaza, and lot numbers is then
ranked; ties between different towns raise `AmbiguousAddressError` unless a written
postal code tells them apart. An area given as `within` discards every municipality and
town outside it. Addresses that lie in one common area are matched together, and the
narrowest area enclosing a candidate of every address decides those ambiguous on their
own. A name alone is looked up instead of matched: every prefecture, municipality, oaza,
and koaza whose whole name it is is listed.

## Components

| Component | Responsibility |
| --- | --- |
| [area_matcher.py](area_matcher.py) | `AreaMatcher`: builds, ranks, and checks readings of an address and returns an `AddressMatch`, or raises `AmbiguousAddressError` with the candidate codes; `find` returns `None` instead of raising for an unmatched or ambiguous address, and `interpret` returns the failure |
| [group_matcher.py](group_matcher.py) | `GroupMatcher`: finds the narrowest common area of a group of addresses and matches the ambiguous ones within it |
| [name_searcher.py](name_searcher.py) | `NameSearcher`: lists every prefecture, municipality, oaza, and koaza that bears a name |
| [municipality_name_index.py](municipality_name_index.py) | `MunicipalityNameIndex`: prefecture and municipality names with their abbreviations, built on first use; one instance is shared by `AreaMatcher` and `NameSearcher` |
| [town_name_index.py](town_name_index.py) | `TownNameIndex`: oaza names nationwide and per municipality, and koaza names per oaza reading, each built on first use |
| [name_index.py](name_index.py) | `NameIndex`: tiered prefix index of oaza or koaza names |
| [candidate_set.py](candidate_set.py) | `CandidateSet`: towns compatible with a partial reading and the loosest `MatchTier` used |
| [town_interpretation.py](town_interpretation.py) | `TownInterpretation`: a complete reading and its ranking key |
| [municipality_match.py](municipality_match.py) | `MunicipalityMatch`: municipalities matching the leading name and remaining text |
| [town_source.py](town_source.py) | `TownSource`: protocol of the municipality, town, oaza, and koaza name lookups that matching needs, implemented by `TownRepository` |
