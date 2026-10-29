# tests

## Overview

Pytest suite. End-to-end tests run against an in-memory database loaded with a small
sample town master that uses the ABR column layout. Local government codes and the town
IDs of Tokyo are real; other town IDs, postal codes, and some readings are illustrative.

## Components

| Component | Responsibility |
| --- | --- |
| [conftest.py](conftest.py) | `importer`, `codec`, and `located_codec` fixtures backed by the sample datasets |
| [fixtures/mt_town_sample.csv](fixtures/mt_town_sample.csv) | Sample town master in ABR format |
| [fixtures/positions/](fixtures/positions/) | Sample position extensions and block, residence, and parcel masters with illustrative points |
| [test_locate.py](test_locate.py) | Representative points, fallback, lot systems, datums, and position imports |
| [test_address_codec.py](test_address_codec.py) | Encoding, decoding, formats including the automatic lot notation, and error cases |
| [test_match_details.py](test_match_details.py) | Match tiers, ambiguity candidates, error bases, `resolve`, and `Address` validation |
| [test_address_code.py](test_address_code.py) | Code parsing, validation, levels, lineage, containment, and prefecture codes |
| [test_text_normalizer.py](test_text_normalizer.py) | Normalization of notation variants |
| [test_kanji_numeral.py](test_kanji_numeral.py) | Kanji numeral conversion |
| [test_lot_number_parser.py](test_lot_number_parser.py) | Lot number notations |
| [test_storage.py](test_storage.py) | Town master import, numbering systems, abolished rows, orphaned positions, read-only opening, and database identification |
| [test_cli.py](test_cli.py) | Command line commands, standard input, and JSON Lines output |
| [test_postal_code.py](test_postal_code.py) | Postal code extraction, disambiguation, and output |
| [test_download.py](test_download.py) | Download plans, distributed files, atomic downloads from a `file://` mirror, failed and truncated downloads, and the `download` command |
| [test_import_log.py](test_import_log.py) | Import log of datasets, digests, and the `info` command |
| [test_kana.py](test_kana.py) | Katakana readings in decoded addresses |
| [test_lot_verification.py](test_lot_verification.py) | Lot number verification against imported masters |
| [test_nearest.py](test_nearest.py) | Nearest address search |
| [test_town_source.py](test_town_source.py) | Matching on an in-memory `TownSource` without a database |
| [test_import_files.py](test_import_files.py) | Dataset detection, ordering and deduplication of `import_files`, transaction rollback, and the `import` command |
| [test_database_cache.py](test_database_cache.py) | Building, reusing, and failed builds of the default database, lots added on demand, and its use by `AddressCodec.open` and the command line |
| [test_postal_lookup.py](test_postal_lookup.py) | Postal code parsing, towns by postal code, and the `postal` command |
| [test_round_trip.py](test_round_trip.py) | Property-based decode and encode round trip over the sample towns |
