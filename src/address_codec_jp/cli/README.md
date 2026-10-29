# cli

## Overview

Command line front end installed as `address-codec-jp`.

## Components

| Component | Responsibility |
| --- | --- |
| [command_line_interface.py](command_line_interface.py) | `CommandLineInterface`: argument parsing and command execution |
| [command_arguments.py](command_arguments.py) | `CommandArguments`: typed argument namespace |
| [command.py](command.py) | `Command`: `import`, `encode`, `decode`, `import-positions`, and `locate` sub-commands |

## Examples

```bash
address-codec-jp --database towns.sqlite3 import mt_town_all.csv.zip
address-codec-jp --database towns.sqlite3 encode "千代田区丸の内1-2-3"
address-codec-jp --database towns.sqlite3 decode 131016-0001001-2-3 --numeral kanji
address-codec-jp --database towns.sqlite3 import-positions mt_town_pos_pref13.csv.zip
address-codec-jp --database towns.sqlite3 locate "千代田区丸の内1-2-3" --crs wgs84
```
