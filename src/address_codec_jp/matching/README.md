# matching

## Overview

Identifies the most specific registered area at the start of a normalized address.
The municipality is found by longest prefix, and a name shared by several
municipalities is resolved by the town name. Every reading of oaza, chome, koaza, and
lot numbers is then ranked; ties between different towns raise `AmbiguousAddressError`
unless a written postal code tells them apart.

## Components

| Component | Responsibility |
| --- | --- |
| [area_matcher.py](area_matcher.py) | `AreaMatcher`: builds, ranks, and checks readings of an address and returns an `AddressMatch`, or raises `AmbiguousAddressError` with the candidate codes |
| [name_index.py](name_index.py) | `NameIndex`: tiered prefix index of oaza or koaza names |
| [candidate_set.py](candidate_set.py) | `CandidateSet`: towns compatible with a partial reading and the loosest `MatchTier` used |
| [town_interpretation.py](town_interpretation.py) | `TownInterpretation`: a complete reading and its ranking key |
| [municipality_match.py](municipality_match.py) | `MunicipalityMatch`: municipalities matching the leading name and remaining text |
| [town_source.py](town_source.py) | `TownSource`: protocol of the municipality and town lookups that matching needs, implemented by `TownRepository` |
