# tests

## Overview

Pytest suite. End-to-end tests run against an in-memory database loaded with a small
sample town master that uses the ABR column layout. Local government codes in the sample
are real; town IDs, postal codes, and some readings are illustrative.

## Components

| Component | Responsibility |
| --- | --- |
| [conftest.py](conftest.py) | `codec` and `located_codec` fixtures backed by the sample datasets |
| [fixtures/mt_town_sample.csv](fixtures/mt_town_sample.csv) | Sample town master in ABR format |
| [fixtures/positions/](fixtures/positions/) | Sample position extensions and block, residence, and parcel masters with illustrative points |
| [test_locate.py](test_locate.py) | Representative points, fallback, lot systems, datums, and position imports |
| [test_address_codec.py](test_address_codec.py) | Encoding, decoding, formats, and error cases |
| [test_address_code.py](test_address_code.py) | Code parsing and validation |
| [test_text_normalizer.py](test_text_normalizer.py) | Normalization of notation variants |
| [test_kanji_numeral.py](test_kanji_numeral.py) | Kanji numeral conversion |
| [test_lot_number_parser.py](test_lot_number_parser.py) | Lot number notations |
| [test_storage.py](test_storage.py) | Town master import, abolished rows, orphaned positions, and schema versions |
| [test_cli.py](test_cli.py) | Command line commands, standard input, and JSON Lines output |
| [test_postal_code.py](test_postal_code.py) | Postal code extraction, disambiguation, and output |
| [test_kana.py](test_kana.py) | Katakana readings in decoded addresses |
| [test_lot_verification.py](test_lot_verification.py) | Lot number verification against imported masters |
| [test_nearest.py](test_nearest.py) | Nearest address search |
| [test_round_trip.py](test_round_trip.py) | Property-based decode and encode round trip over the sample towns |
