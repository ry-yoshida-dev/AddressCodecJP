# query

## Overview

Queries shared by the command line and the web API: each names a query by its
`QueryOperation`, takes its options as `QueryOptions`, and answers it through
`QueryRunner`, plugging in its own `TextInterpreter` for malformed input and
`QueryGuard` for the datasets a query may read.

## Components

| Component | Responsibility |
| --- | --- |
| [runner.py](runner.py) | `QueryRunner`: answers one input of any operation; an empty listing is not found |
| [record.py](record.py) | `QueryRecord`: JSON fields, tab-separated rows, and the lot and shapes an answer was drawn from |
| [text_interpreter.py](text_interpreter.py) | `TextInterpreter`: protocol of how a front end reports malformed input |
| [direct_interpreter.py](direct_interpreter.py) | `DirectInterpreter`: interpreter that lets parse errors through unchanged |
| [guard.py](guard.py) | `QueryGuard`: protocol of the dataset checks of a front end |
| [pass_through_guard.py](pass_through_guard.py) | `PassThroughGuard`: guard that admits every dataset |
| [operation.py](operation.py) | `QueryOperation`: the queries, named like the command line sub-commands and the batch operations of the web API |
| [options.py](options.py) | `QueryOptions`: format, datum, distance, verification, parcel, and geometry options |

## Examples

```python
from address_codec_jp import AddressCodec
from address_codec_jp.frontends.query import (
    DirectInterpreter,
    PassThroughGuard,
    QueryOperation,
    QueryOptions,
    QueryRunner,
)

with AddressCodec.open() as codec:
    runner = QueryRunner(codec, DirectInterpreter(), PassThroughGuard())
    record = runner.run(QueryOperation.LOCATE, "千代田区丸の内1-9-1", QueryOptions())
    print(record.fields)
```
