# Web API

OpenAPI documentation is served at `/docs`.

## Environment variables

| Variable | Default | Meaning |
| --- | --- | --- |
| `ADDRESS_CODEC_JP_API_PUBLISHER` | required | Organization that processes and serves the data, named in every credit |
| `ADDRESS_CODEC_JP_CACHE_DIR` | user cache directory | Prepared cache |
| `ADDRESS_CODEC_JP_API_THREADS` | `4` | Worker threads per process, each with its own codec |
| `ADDRESS_CODEC_JP_API_MAX_BATCH_SIZE` | `1000` | Inputs per batch request |
| `ADDRESS_CODEC_JP_API_MAX_INPUT_LENGTH` | `1000` | Characters per input |
| `ADDRESS_CODEC_JP_API_BUSY_TIMEOUT` | `1` | Seconds a query waits while another process writes the database before it is answered with 503 |
| `ADDRESS_CODEC_JP_API_COVERAGE_REQUIRED` | `true` | Answer 503 instead of falling back to an enclosing area when a municipality lacks prepared data |

## Endpoints

| Endpoint | Query |
| --- | --- |
| `GET /v1/codes?address=` | Encode; `verify_lot=true` checks the lot numbers, `partial=true` returns the municipality or prefecture with the unread text as `remainder` when no town matches |
| `GET /v1/codes/{code}` | Decode; `numeral`, `lot`, `width`, `prefecture`, `county`, `kana`, `postal_code` |
| `GET /v1/locations?address=`, `GET /v1/codes/{code}/location` | Representative point; `crs`, `partial` for an address |
| `GET /v1/nearest?coordinate=lat,lon` | Nearest address; `crs`, `max_distance` |
| `GET /v1/postal-codes/{postal_code}` | Towns of a postal code; decode format options |
| `GET /v1/codes/{code}/children` | Areas directly under a prefecture, municipality, or oaza; decode format options |
| `GET /v1/names/{name}` | Every area that bears a name; decode format options |
| `GET /v1/areas?address=`, `GET /v1/codes/{code}/area` | Shape; `geometry=false` omits the GeoJSON, `partial` for an address |
| `GET /v1/areas-at?coordinate=lat,lon` | Containing towns; `parcels=true` adds parcels, `geometry=true` adds GeoJSON |
| `POST /v1/batch` | `{"operation": "locate", "inputs": [...]}`, options as for the GET endpoint; operations named like the commands (`locate-code`, `area-code`, `areas-at`, ...); per-input `status` on failure |
| `GET /health` | Readiness and the number of prepared municipalities |

Responses carry the fields of the `jsonl` [command line output](command-line.md) plus `attribution`, the credits of the datasets used.

## Errors

Body: `{"error", "error_type"}`.

| Status | When |
| --- | --- |
| 400 | `InvalidRequestError`: malformed input or option, input over the length limit, number too large, failed validation |
| 404 | Not found, including a coordinate outside every prepared boundary |
| 409 | Ambiguous, with `candidates` |
| 503 | Data not prepared, database deleted, or locked during an update (with `Retry-After`) |
| 500 | Malformed data such as `RegistryFormatError`, or an unexpected exception |
