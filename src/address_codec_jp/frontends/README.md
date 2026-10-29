# frontends

## Overview

Front ends built on `AddressCodec` and `DatabaseCache`: the command line, the optional
web API, and the JSON fields of results and errors that both share.

## Components

| Component | Responsibility |
| --- | --- |
| [cli/](cli/) | Command line interface installed as `address-codec-jp` |
| [api/](api/) | Optional FastAPI web API on a prepared cache (`api` extra) |
| [serialization/](serialization/) | JSON fields of codec results and errors |
