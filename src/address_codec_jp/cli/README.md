# cli

## Overview

Command line front end installed as `address-codec-jp`. Import commands go through
`RegistryImporter`, and query commands through a read-only `AddressCodec`. Query commands
read their inputs from the arguments, or line by line from standard input, and write
tab-separated text or JSON Lines; blank input lines are reported as errors, so JSON Lines
output stays aligned with the input. Without `--database`, every command uses the
database of `DatabaseCache`, built on first use.

## Components

| Component | Responsibility |
| --- | --- |
| [command_line_interface.py](command_line_interface.py) | `CommandLineInterface`: argument parsing and command execution |
| [command_arguments.py](command_arguments.py) | `CommandArguments`: typed argument namespace with enum-valued options |
| [enum_argument.py](enum_argument.py) | `EnumArgument`: converts an option value to an enum member by case-insensitive name |
| [command.py](command.py) | `Command`: `import`, `import-area`, `download`, `info`, `cache`, `encode`, `decode`, `locate`, `nearest`, `postal`, `area`, and `area-at` sub-commands |
| [cache_action.py](cache_action.py) | `CacheAction`: `info`, `clear`, `refresh`, or `prepare` of the `cache` command |
| [output_format.py](output_format.py) | `OutputFormat`: `tsv` or `jsonl` output of query commands |
| [output_value.py](output_value.py) | `OutputValue`: value types written to JSON Lines |
| [record_writer.py](record_writer.py) | `RecordWriter`: writes one result or error per input, with the error type and the candidates of an ambiguous address in JSON Lines |
| [coordinate_text.py](coordinate_text.py) | `CoordinateText`: parses `latitude,longitude` inputs |

## Examples

```bash
address-codec-jp encode "千代田区内幸町1-6-1"
address-codec-jp decode 131016-0011001-2-3 --numeral kanji
address-codec-jp decode 131016-0001001-6-1 --kana
address-codec-jp postal 060-0042
address-codec-jp nearest 35.6812,139.7671 --max-distance 500
address-codec-jp download data --prefecture 13 --import
address-codec-jp encode "千代田区内幸町1-6-1" --verify-lot
address-codec-jp locate "千代田区内幸町1-6-1" --crs wgs84
address-codec-jp area "千代田区丸の内1-9-1"
address-codec-jp area-at 35.6812,139.7671 --parcels --output jsonl
address-codec-jp info
address-codec-jp cache prepare --prefecture 13 --parcels
address-codec-jp cache refresh
cut -f1 addresses.tsv | address-codec-jp encode --output jsonl
address-codec-jp --database towns.sqlite3 import data/*.zip
address-codec-jp --database towns.sqlite3 import-area --lg-code 131016 census_boundary_131016.zip
```
