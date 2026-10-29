# errors

## Overview

Exception hierarchy of AddressCodecJP. Every error derives from `AddressCodecError` and
from the most specific built-in exception, so `except LookupError` keeps working.

## Components

| Component | Responsibility |
| --- | --- |
| [address_codec_error.py](address_codec_error.py) | `AddressCodecError`: base of all library errors |
| [address_not_found_error.py](address_not_found_error.py) | `AddressNotFoundError` (`LookupError`): address, code, or lot is not registered |
| [ambiguous_address_error.py](ambiguous_address_error.py) | `AmbiguousAddressError` (`LookupError`): several areas or lots fit; carries the candidate codes |
| [dataset_not_imported_error.py](dataset_not_imported_error.py) | `DatasetNotImportedError` (`RuntimeError`): a required dataset has not been imported |
| [position_not_found_error.py](position_not_found_error.py) | `PositionNotFoundError` (`LookupError`): no representative point fits |
| [reading_not_found_error.py](reading_not_found_error.py) | `ReadingNotFoundError` (`LookupError`): katakana reading of a name is missing |
| [registry_format_error.py](registry_format_error.py) | `RegistryFormatError` (`ValueError`): registry file is not the expected dataset or is malformed |
| [unsupported_database_error.py](unsupported_database_error.py) | `UnsupportedDatabaseError` (`ValueError`): database was not created by this version |

## Examples

```python
from address_codec_jp import AddressCodec, AmbiguousAddressError

with AddressCodec.open("towns.sqlite3") as codec:
    try:
        codec.encode("府中市")
    except AmbiguousAddressError as error:
        print([str(code) for code in error.candidates])
```
