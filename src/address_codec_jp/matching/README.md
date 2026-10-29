# matching

## Overview

Identifies the most specific registered area at the start of a normalized address.
The prefecture or municipality is found by longest prefix, falling back to shorter
municipality names confirmed by a town name; a name shared by several
municipalities, such as a designated city without its ward, is resolved by the town
name. For the rest, every reading
of oaza, chome, koaza, and lot numbers is built and ranked; ties between different towns
are rejected as ambiguous instead of being resolved silently.

## Components

| Component | Responsibility |
| --- | --- |
| [area_matcher.py](area_matcher.py) | `AreaMatcher`: builds, ranks, and checks readings of an address |
| [name_index.py](name_index.py) | `NameIndex`: tiered prefix index of oaza or koaza names |
| [match_tier.py](match_tier.py) | `MatchTier`: exact, prefix-insensitive, and variant-folded comparison |
| [candidate_set.py](candidate_set.py) | `CandidateSet`: towns compatible with a partial reading |
| [town_interpretation.py](town_interpretation.py) | `TownInterpretation`: a complete reading and its ranking key |
| [area_match.py](area_match.py) | `AreaMatch`: matched prefecture, municipality, town, lot numbers, and remainder |
| [municipality_match.py](municipality_match.py) | `MunicipalityMatch`: municipalities matching the leading name and remaining text |
