# frontends

## Overview

Tests of the command line, the web API, and their shared query runner. Fixtures come
from [fixture_paths.py](../fixture_paths.py) and [conftest.py](../conftest.py).

## Components

| Component | Responsibility |
| --- | --- |
| [test_cli.py](test_cli.py) | Command line commands, standard input, and JSON Lines output |
| [test_api.py](test_api.py) | Web API endpoints, status codes, hidden server faults, coverage of unprepared municipalities, batches, dataset credits, settings, and reopening of a replaced database |
| [test_query_runner.py](test_query_runner.py) | Shared query runner with its interpreters and guards, including the coverage checks of lots, nearest addresses, and shapes |
