# tests

## Overview

Pytest suite. End-to-end tests run against an in-memory database loaded with a small
sample town master that uses the ABR column layout. Local government codes and the town
IDs of Tokyo and Kyoto are real; other town IDs, postal codes, and some readings are illustrative.
The census boundary of Chiyoda is the real e-Stat file (令和2年国勢調査 町丁・字等境界データ,
Statistics Bureau of Japan); the registry map sheets are written by hand in the format of
the Ministry of Justice. Tests are grouped by the package they exercise; end-to-end
tests of the `AddressCodec` facade stay at the top level.

## Components

| Component | Responsibility |
| --- | --- |
| [conftest.py](conftest.py) | `importer`, `codec`, and `located_codec` fixtures backed by the sample datasets |
| [fixture_paths.py](fixture_paths.py) | Paths of the fixture directory and the sample town master |
| [address/](address/) | Tests of the address code values |
| [text/](text/) | Tests of normalization, matching, and formatting of address text, mostly through `AddressCodec` |
| [geocoding/](geocoding/) | Tests of representative points, nearest addresses, lot verification, and area shapes |
| [database/](database/) | Tests of the SQLite storage, the importers, the lookup of registered areas, and the default database cache |
| [datasets/](datasets/) | Tests of downloading the registry datasets |
| [frontends/](frontends/) | Tests of the command line, the web API, and their shared query runner |
| [fixtures/mt_town_sample.csv](fixtures/mt_town_sample.csv) | Sample town master in ABR format |
| [fixtures/areas/](fixtures/areas/) | Census boundary of Chiyoda and registry map sheets of Miyoshi on public and local coordinates |
| [fixtures/positions/](fixtures/positions/) | Sample position extensions and block, residence, and parcel masters with illustrative points |
| [test_address_codec.py](test_address_codec.py) | Encoding, decoding, formats including the automatic lot notation, and error cases |
| [test_round_trip.py](test_round_trip.py) | Property-based decode and encode round trip over the sample towns |
