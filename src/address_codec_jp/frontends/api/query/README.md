# query

## Overview

Queries of the web API, answered through the shared `QueryRunner` of the
[query](../../query/) package on a thread's codec, checked against the cache's coverage,
and credited with the datasets used.

## Components

| Component | Responsibility |
| --- | --- |
| [handler.py](handler.py) | `QueryHandler`: runs one or many queries, rejects overlong inputs, and credits the datasets used |
| [coverage_guard.py](coverage_guard.py) | `CoverageGuard`: rejects queries that need lots, boundaries, or registry maps the cache does not hold |
| [answer.py](answer.py) | `QueryAnswer`: response fields and their credits |
