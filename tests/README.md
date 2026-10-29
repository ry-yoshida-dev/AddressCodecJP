# tests

## Overview

Pytest suite. End-to-end tests run against an in-memory database loaded with a small
sample town master that uses the ABR column layout. Local government codes in the sample
are real; town IDs are illustrative.

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
