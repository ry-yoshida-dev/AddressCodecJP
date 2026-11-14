# normalization

## Overview

Converts address text into a canonical form so that notation variants compare equal,
and parses lot numbers from the normalized text.

## Components

| Component | Responsibility |
| --- | --- |
| [text_normalizer.py](text_normalizer.py) | `TextNormalizer`: removal of invisible characters and quotes, width, dash, kanji numeral, Sapporo grid abbreviation, and variant character normalization, extraction of a leading postal code, recovery of the raw text behind a normalized suffix, and the reason an input normalizes to nothing |
| [kanji_variants.py](kanji_variants.py) | `KanjiVariants`: variant kanji of place names (`藪`/`薮`, `竜`/`龍`, `塩竈`/`塩釜`) and the form each folds to |
| [kanji_numeral.py](kanji_numeral.py) | `KanjiNumeral`: conversion between integers and kanji numerals |
| [lot_number_parser.py](lot_number_parser.py) | `LotNumberParser`: parses up to three lot numbers such as `2番3号`, `124番地1の1` and `2-3`, and the numbering system their notation marks, leaving floor and building numbers such as `3階` or `2号館` unread |
| [lot_parse_result.py](lot_parse_result.py) | `LotParseResult`: parsed lot numbers, the numbering system of their notation, and remaining text |

## Examples

```python
from address_codec_jp.text.normalization import TextNormalizer

TextNormalizer().normalize("丸の内一丁目２ー３")
# '丸の内1丁目2-3'
```
