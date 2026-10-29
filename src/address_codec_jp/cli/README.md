# cli

## Overview

Command line front end installed as `address-codec-jp`. Query commands read their inputs
from the arguments, or one per line from standard input, and write tab-separated text or
JSON Lines.

## Components

| Component | Responsibility |
| --- | --- |
| [command_line_interface.py](command_line_interface.py) | `CommandLineInterface`: argument parsing and command execution |
| [command_arguments.py](command_arguments.py) | `CommandArguments`: typed argument namespace |
| [command.py](command.py) | `Command`: `import`, `encode`, `decode`, `import-positions`, `locate`, and `nearest` sub-commands |
| [output_format.py](output_format.py) | `OutputFormat`: `tsv` or `jsonl` output of query commands |
| [output_value.py](output_value.py) | `OutputValue`: value types written to JSON Lines |
| [record_writer.py](record_writer.py) | `RecordWriter`: writes one result or error per input |
| [coordinate_text.py](coordinate_text.py) | `CoordinateText`: parses `latitude,longitude` inputs |

## Examples

```bash
address-codec-jp --database towns.sqlite3 import mt_town_all.csv.zip
address-codec-jp --database towns.sqlite3 encode "千代田区丸の内1-2-3" --verify-lot
address-codec-jp --database towns.sqlite3 decode 131016-0001001-2-3 --numeral kanji
address-codec-jp --database towns.sqlite3 decode 131016-0001001-2-3 --kana --postal-code
address-codec-jp --database towns.sqlite3 import-positions mt_town_pos_pref13.csv.zip
address-codec-jp --database towns.sqlite3 locate "千代田区丸の内1-2-3" --crs wgs84
address-codec-jp --database towns.sqlite3 nearest 35.6812,139.7671 --max-distance 500
cut -f1 addresses.tsv | address-codec-jp --database towns.sqlite3 encode --output jsonl
```
