# reading

## Overview

Reads one normalized address into its municipality, town, and lot numbers, ranks the
readings, and rejects an address that several readings fit equally well.

## Components

| Component | Responsibility |
| --- | --- |
| [area_matcher.py](area_matcher.py) | `AreaMatcher`: combines the municipality and town readings, ranks them, and returns an `AddressMatch` or the `AddressNotFoundError` or `AmbiguousAddressError` |
| [municipality_reader.py](municipality_reader.py) | `MunicipalityReader`: reads the prefecture and municipality names and narrows them to an area or by a postal code |
| [town_reader.py](town_reader.py) | `TownReader`: reads every combination of oaza, chome, koaza, and lot numbers after a municipality |
| [street_direction_reader.py](street_direction_reader.py) | `StreetDirectionReader`: finds where a Kyoto street direction ends, matches it against registered ones with notation variants folded, and ranks oaza of one name by the streets an unregistered direction names |
| [municipality_match.py](municipality_match.py) | `MunicipalityMatch`: municipalities matching the leading name and remaining text |
| [town_interpretation.py](town_interpretation.py) | `TownInterpretation`: a complete reading and its ranking key |
