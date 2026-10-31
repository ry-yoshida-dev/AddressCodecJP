# query

## Overview

Queries of the web API. `QueryHandler` answers a `QueryOperation` with its `QueryOptions`
through the shared `QueryRunner` of the [query](../../query/) package on a thread's codec.
Malformed inputs are reported as invalid by `InputInterpreter`, and with coverage required,
`CoverageGuard` rejects municipalities the cache does not hold. The records of the inputs
become a `QueryAnswer` with the credits of the datasets used.

## Components

| Component | Responsibility |
| --- | --- |
| [handler.py](handler.py) | `QueryHandler`: runs one or many queries, rejects overlong inputs, and credits the datasets used |
| [coverage_guard.py](coverage_guard.py) | `CoverageGuard`: rejects queries that need lots, boundaries, or registry maps the cache does not hold |
| [answer.py](answer.py) | `QueryAnswer`: response fields and their credits |
