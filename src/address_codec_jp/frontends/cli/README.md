# cli

## Overview

Command line front end installed as `address-codec-jp`, with import and cache
maintenance commands and query commands that give the same fields as the web API. See
[docs/command-line.md](../../../../docs/command-line.md) for the output format and
exit statuses, and `address-codec-jp <command> -h` for the options.

## Components

| Component | Responsibility |
| --- | --- |
| [command_line_interface.py](command_line_interface.py) | `CommandLineInterface`: dispatches a parsed command and answers the inputs of query commands |
| [parser_factory.py](parser_factory.py) | `ParserFactory`: builds the argument parser of all sub-commands |
| [query_input.py](query_input.py) | `QueryInput`: kind of the inputs of a query sub-command, with its placeholder and help |
| [subcommand_registry.py](subcommand_registry.py) | `SubcommandRegistry`: protocol of the sub-command group a parser adds commands to |
| [database_maintainer.py](database_maintainer.py) | `DatabaseMaintainer`: runs `import`, `import-area`, `download`, `info`, and `cache` |
| [command_arguments.py](command_arguments.py) | `CommandArguments`: typed argument namespace with enum-valued options, turned into `QueryOptions` for query commands |
| [enum_argument.py](enum_argument.py) | `EnumArgument`: converts an option value to an enum member by case-insensitive name |
| [maintenance_command.py](maintenance_command.py) | `MaintenanceCommand`: `import`, `import-area`, `download`, `info`, and `cache`; the query sub-commands are the `QueryOperation` values |
| [exit_status.py](exit_status.py) | `ExitStatus`: success, input failure, usage error, or fatal error |
| [cache_action.py](cache_action.py) | `CacheAction`: `info`, `clear`, `refresh`, or `prepare` of the `cache` command |
| [output_format.py](output_format.py) | `OutputFormat`: `tsv` or `jsonl` output of query commands |
| [record_writer.py](record_writer.py) | `RecordWriter`: writes one result or error record per input on standard output, led by the input in tab-separated text |

## Examples

```bash
address-codec-jp encode "千代田区内幸町1-6-1" --verify-lot
address-codec-jp locate "千代田区内幸町1-6-1" --crs wgs84
address-codec-jp areas-at 35.6812,139.7671 --parcels --geometry --output jsonl
cut -f1 addresses.tsv | address-codec-jp encode --output jsonl
address-codec-jp cache prepare --prefecture 13 --parcels
address-codec-jp --database towns.sqlite3 import data/*.zip
```
