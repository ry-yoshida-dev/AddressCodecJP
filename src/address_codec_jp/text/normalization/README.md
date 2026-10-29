# normalization

## Overview

Converts address text into a canonical form so that notation variants compare equal,
and parses lot numbers from the normalized text.

## Components

| Component | Responsibility |
| --- | --- |
| [text_normalizer.py](text_normalizer.py) | `TextNormalizer`: width, dash, kanji numeral, and variant character normalization, and extraction of a leading postal code |
| [kanji_numeral.py](kanji_numeral.py) | `KanjiNumeral`: conversion between integers and kanji numerals |
| [lot_number_parser.py](lot_number_parser.py) | `LotNumberParser`: parses `2番3号`, `2番地の3`, `2-3` and similar |
| [lot_parse_result.py](lot_parse_result.py) | `LotParseResult`: parsed lot numbers and remaining text |

## Examples

```python
from address_codec_jp.text.normalization import TextNormalizer

TextNormalizer().normalize("丸の内一丁目２ー３")
# '丸の内1丁目2-3'
```
