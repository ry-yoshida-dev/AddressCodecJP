# api

## Overview

Optional web API built with FastAPI, installed with the `api` extra. It serves a cache
prepared beforehand and never downloads while handling requests. Queries run on a
fixed set of worker threads, each with its own `AddressCodec`, because a codec must be
used in the thread that opened it. When the database file is replaced, e.g. by
`address-codec-jp cache refresh` from another process, each thread reopens its codec
before its next query; when it is extended in place by `cache prepare`, the coverage is
read again.

With `is_coverage_required` (the default), a query that needs the blocks, residences,
or town boundaries of a municipality that the cache does not hold fails with HTTP 503
instead of silently falling back to an enclosing area. Every successful response
carries `attribution`, the credits that the terms of use of its datasets require: the
source, that the data was processed, and the publisher who processed it.

Only a failure to interpret the request is answered with 400 and its message. A
library error about malformed data, such as `RegistryFormatError`, and any unexpected
exception are logged and answered with a generic 500 body. A batch reports failures
caused by an input in place of its result; a fault of the server fails the request.

## Components

| Component | Responsibility |
| --- | --- |
| [application_factory.py](application_factory.py) | `ApplicationFactory`: builds the FastAPI application, checks the cache at start, and maps errors to responses |
| [address_routes.py](address_routes.py) | `AddressRoutes`: the `/v1` endpoints and `/health` |
| [codec_pool.py](codec_pool.py) | `CodecPool`: worker threads with one codec each, reopened when the database file is replaced |
| [query_handler.py](query_handler.py) | `QueryHandler`: runs one or many queries on a thread's codec and enforces coverage |
| [query_operation.py](query_operation.py) | `QueryOperation`: the queries of the API |
| [query_options.py](query_options.py) | `QueryOptions`: format, datum, distance, parcel, and geometry options |
| [query_answer.py](query_answer.py) | `QueryAnswer`: response fields and their credits |
| [dataset_coverage.py](dataset_coverage.py) | `DatasetCoverage`: municipalities whose lots and boundaries the cache holds, and the dates of their maps |
| [credit_writer.py](credit_writer.py) | `CreditWriter`: credits in the form required by the terms of use, with municipality names and map dates |
| [data_source.py](data_source.py) | `DataSource`: Address Base Registry, parcel master, census boundaries, or registry maps |
| [data_attribution.py](data_attribution.py) | `DataAttribution`: dataset to credit and the municipality it was used for |
| [query_result.py](query_result.py) | `QueryResult`: fields of one query and the datasets it used |
| [error_status.py](error_status.py) | `ErrorStatus`: HTTP status of each error |
| [invalid_request_error.py](invalid_request_error.py) | `InvalidRequestError`: input or option that cannot be interpreted (400) |
| [input_interpreter.py](input_interpreter.py) | `InputInterpreter`: parses request values, turning their `ValueError` into `InvalidRequestError` |
| [service_settings.py](service_settings.py) | `ServiceSettings`: publisher, threads, batch size, and coverage policy, read from the environment |
| [format_parameters.py](format_parameters.py) | `FormatParameters`: request parameters of the address format |
| [batch_request.py](batch_request.py) | `BatchRequest`: body of `POST /v1/batch` |
| [file_signature.py](file_signature.py) | `FileSignature`: tells a replaced database file from a modified one |
| [opened_codec.py](opened_codec.py) | `OpenedCodec`: codec of a thread and the file it was opened on |

## Examples

```bash
ADDRESS_CODEC_JP_API_PUBLISHER="Example Maps Inc." \
    uvicorn --factory address_codec_jp.api:ApplicationFactory.from_environment --workers 4
```

```python
from pathlib import Path

from address_codec_jp.api import ApplicationFactory, ServiceSettings

application = ApplicationFactory(
    ServiceSettings(
        publisher="Example Maps Inc.",
        cache_directory=Path("/var/lib/addresses"),
        thread_count=4,
    )
).create()
```
