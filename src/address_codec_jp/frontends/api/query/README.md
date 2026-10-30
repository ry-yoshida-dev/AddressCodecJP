# query

## Overview

Queries of the web API. `QueryHandler` runs a `QueryOperation` with its `QueryOptions` on a
thread's codec, collects the `QueryResult` of each input, and turns them into a
`QueryAnswer` with the credits of the datasets used.

## Components

| Component | Responsibility |
| --- | --- |
| [handler.py](handler.py) | `QueryHandler`: runs one or many queries on a thread's codec, enforces coverage, and rejects overlong inputs |
| [operation.py](operation.py) | `QueryOperation`: the queries of the API, named like the batch operations and the command line sub-commands |
| [options.py](options.py) | `QueryOptions`: format, datum, distance, parcel, and geometry options |
| [answer.py](answer.py) | `QueryAnswer`: response fields and their credits |
| [result.py](result.py) | `QueryResult`: fields of one query and the datasets it used |
