# text

## Overview

Tests of normalization, matching, and formatting of address text, mostly through
`AddressCodec`. Fixtures come from [fixture_paths.py](../fixture_paths.py) and
[conftest.py](../conftest.py).

## Components

| Component | Responsibility |
| --- | --- |
| [test_text_normalizer.py](test_text_normalizer.py) | Normalization of notation variants |
| [test_kanji_numeral.py](test_kanji_numeral.py) | Kanji numeral conversion |
| [test_lot_number_parser.py](test_lot_number_parser.py) | Lot number notations |
| [test_match_details.py](test_match_details.py) | Match tiers, ambiguity candidates, `AreaMatcher.find`, error bases, `resolve`, and `Address` validation |
| [test_town_source.py](test_town_source.py) | Matching on an in-memory `TownSource` without a database |
| [test_group_match.py](test_group_match.py) | Matching within a given area, and groups of addresses decided by their common area |
| [test_name_search.py](test_name_search.py) | Every area that bears a name, narrowing by a leading area or `within`, and the `name` command |
| [test_postal_code.py](test_postal_code.py) | Postal code extraction, disambiguation, and output |
| [test_kana.py](test_kana.py) | Katakana readings in decoded addresses |
| [test_street_direction.py](test_street_direction.py) | Kyoto street directions before and after the oaza, lot numbers on the oaza, notation variants, unregistered directions, and their decoding |
