# Command line output

| `--output` | Format |
| --- | --- |
| `tsv` (default) | Tab-separated lines starting with the input: one line per result row; the input alone for an empty result; input, `ERROR`, error type, message for a failure |
| `jsonl` | One JSON object per input, with the fields of the [web API](web-api.md) |

| Exit status | Meaning |
| --- | --- |
| 0 | Every input was answered |
| 1 | Some input failed |
| 2 | Invalid arguments |
| 3 | The command could not run or stopped, such as when the database cannot be opened |
