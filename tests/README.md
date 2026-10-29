# tests

## Overview

Pytest suite. End-to-end tests run against an in-memory database loaded with a small
sample town master that uses the ABR column layout. Local government codes in the sample
are real; town IDs are illustrative.

## Components

| Component | Responsibility |
| --- | --- |
| [conftest.py](conftest.py) | `codec` fixture backed by the sample town master |
| [fixtures/mt_town_sample.csv](fixtures/mt_town_sample.csv) | Sample town master in ABR format |
| [test_address_codec.py](test_address_codec.py) | Encoding, decoding, formats, and error cases |
| [test_address_code.py](test_address_code.py) | Code parsing and validation |
| [test_text_normalizer.py](test_text_normalizer.py) | Normalization of notation variants |
| [test_kanji_numeral.py](test_kanji_numeral.py) | Kanji numeral conversion |
| [test_lot_number_parser.py](test_lot_number_parser.py) | Lot number notations |
