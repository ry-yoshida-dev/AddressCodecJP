# cli

## Overview

Command line front end installed as `address-codec-jp`. Import commands go through
`RegistryImporter`, and query commands through a read-only `AddressCodec`. Query commands
read their inputs from the arguments, or line by line from standard input, and write
tab-separated text or JSON Lines, whose fields come from the shared
[serialization](../serialization/) layer. Every input is represented on standard output:
a failed input, a blank line included, is written as an error record and the next input
is processed. Tab-separated lines start with the input; a result of several rows writes
one line per row, an empty result the input alone, and a failure the input, `ERROR`,
the error type, and the message. Without `--database`, every command uses the database
of `DatabaseCache`, built on first use.

The exit status is 0 when every input was answered, 1 when some input failed, 2 for
invalid arguments, and 3 when the command could not run or stopped, such as when the
database cannot be opened.

## Components

| Component | Responsibility |
| --- | --- |
| [command_line_interface.py](command_line_interface.py) | `CommandLineInterface`: dispatches a parsed command and reads the inputs of query commands |
| [parser_factory.py](parser_factory.py) | `ParserFactory`: builds the argument parser of all sub-commands |
| [query_answerer.py](query_answerer.py) | `QueryAnswerer`: answers one input of `encode`, `decode`, `locate`, `locate-code`, `nearest`, `postal`, `children`, `name`, `area`, `area-code`, or `areas-at` |
| [database_maintainer.py](database_maintainer.py) | `DatabaseMaintainer`: runs `import`, `import-area`, `download`, `info`, and `cache` |
| [command_arguments.py](command_arguments.py) | `CommandArguments`: typed argument namespace with enum-valued options |
| [enum_argument.py](enum_argument.py) | `EnumArgument`: converts an option value to an enum member by case-insensitive name |
| [command.py](command.py) | `Command`: `import`, `import-area`, `download`, `info`, `cache`, and the query sub-commands, named like the batch operations of the web API |
| [exit_status.py](exit_status.py) | `ExitStatus`: success, input failure, usage error, or fatal error |
| [cache_action.py](cache_action.py) | `CacheAction`: `info`, `clear`, `refresh`, or `prepare` of the `cache` command |
| [output_format.py](output_format.py) | `OutputFormat`: `tsv` or `jsonl` output of query commands |
| [record_writer.py](record_writer.py) | `RecordWriter`: writes one result or error record per input on standard output, led by the input in tab-separated text |

## Examples

```bash
address-codec-jp encode "千代田区内幸町1-6-1"
address-codec-jp decode 131016-0011001-2-3 --numeral kanji
address-codec-jp decode 131016-0001001-6-1 --kana
address-codec-jp postal 060-0042
address-codec-jp children 130001
address-codec-jp name 府中市
address-codec-jp nearest 35.6812,139.7671 --max-distance 500
address-codec-jp download data --prefecture 13 --import
address-codec-jp encode "千代田区内幸町1-6-1" --verify-lot
address-codec-jp locate "千代田区内幸町1-6-1" --crs wgs84
address-codec-jp locate-code 131016-0011001-2-3
address-codec-jp area "千代田区丸の内1-9-1"
address-codec-jp area-code 131016-0011001 --no-geometry
address-codec-jp areas-at 35.6812,139.7671 --parcels --geometry --output jsonl
address-codec-jp info
address-codec-jp cache prepare --prefecture 13 --parcels
address-codec-jp cache refresh
cut -f1 addresses.tsv | address-codec-jp encode --output jsonl
address-codec-jp --database towns.sqlite3 import data/*.zip
address-codec-jp --database towns.sqlite3 import-area --lg-code 131016 census_boundary_131016.zip
```
