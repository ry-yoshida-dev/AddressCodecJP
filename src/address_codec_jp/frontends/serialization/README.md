# serialization

## Overview

Conversion of `AddressCodec` results and errors to JSON-compatible fields. The command
line (JSON Lines) and the web API write through these classes, so both give the same
fields. Points and shapes carry `is_exact`, which tells whether they stand for the
requested address itself or for an enclosing area.

## Components

| Component | Responsibility |
| --- | --- |
| [result_serializer.py](result_serializer.py) | `ResultSerializer`: fields of matches, decoded addresses, points, nearest addresses, postal code towns, child areas, and area shapes with optional GeoJSON geometry |
| [error_serializer.py](error_serializer.py) | `ErrorSerializer`: message, type name, and the candidates of an ambiguous address |
| [json_value.py](json_value.py) | `JsonValue`: value types written as JSON |
| [coordinate_text.py](coordinate_text.py) | `CoordinateText`: parses `latitude,longitude` inputs |
| [enum_name.py](enum_name.py) | `EnumName`: converts a text value to an enum member by case-insensitive name |

## Examples

```python
from address_codec_jp import AddressCodec
from address_codec_jp.frontends.serialization import ResultSerializer

with AddressCodec.open() as codec:
    serializer = ResultSerializer(codec)
    print(serializer.location(codec.locate("千代田区丸の内1-9-1")))
```
