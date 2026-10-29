# cli

## Overview

Command line front end installed as `address-codec-jp`. Import commands go through
`RegistryImporter`, and query commands through a read-only `AddressCodec`. Query commands
read their inputs from the arguments, or line by line from standard input, and write
tab-separated text or JSON Lines; blank input lines are reported as errors, so JSON Lines
output stays aligned with the input.

## Components

| Component | Responsibility |
| --- | --- |
| [command_line_interface.py](command_line_interface.py) | `CommandLineInterface`: argument parsing and command execution |
| [command_arguments.py](command_arguments.py) | `CommandArguments`: typed argument namespace with enum-valued options |
| [enum_argument.py](enum_argument.py) | `EnumArgument`: converts an option value to an enum member by case-insensitive name |
| [command.py](command.py) | `Command`: `import`, `download`, `info`, `encode`, `decode`, `locate`, `nearest`, and `postal` sub-commands |
| [output_format.py](output_format.py) | `OutputFormat`: `tsv` or `jsonl` output of query commands |
| [output_value.py](output_value.py) | `OutputValue`: value types written to JSON Lines |
| [record_writer.py](record_writer.py) | `RecordWriter`: writes one result or error per input, with the error type and the candidates of an ambiguous address in JSON Lines |
| [coordinate_text.py](coordinate_text.py) | `CoordinateText`: parses `latitude,longitude` inputs |

## Examples

```bash
address-codec-jp --database towns.sqlite3 download data --prefecture 13 --import
address-codec-jp --database towns.sqlite3 import data/*.zip
address-codec-jp --database towns.sqlite3 encode "千代田区内幸町1-6-1" --verify-lot
address-codec-jp --database towns.sqlite3 decode 131016-0011001-2-3 --numeral kanji
address-codec-jp --database towns.sqlite3 decode 131016-0001001-6-1 --kana
address-codec-jp --database towns.sqlite3 postal 060-0042
address-codec-jp --database towns.sqlite3 locate "千代田区内幸町1-6-1" --crs wgs84
address-codec-jp --database towns.sqlite3 nearest 35.6812,139.7671 --max-distance 500
address-codec-jp --database towns.sqlite3 info
cut -f1 addresses.tsv | address-codec-jp --database towns.sqlite3 encode --output jsonl
```
