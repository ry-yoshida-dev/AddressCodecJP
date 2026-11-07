# Database cache

| Platform | Default location |
| --- | --- |
| macOS | `~/Library/Caches/address-codec-jp/towns-v{schema version}.sqlite3` |
| Linux | `~/.cache/address-codec-jp/towns-v{schema version}.sqlite3` |

| Variable | Meaning |
| --- | --- |
| `ADDRESS_CODEC_JP_CACHE_DIR` | Cache directory |
| `ADDRESS_CODEC_JP_BASE_URL` | Address Base Registry download site or a mirror |
| `ADDRESS_CODEC_JP_CENSUS_URL` | URL template of a municipality's census boundary archive, with `{code}` for its five-digit code |
| `ADDRESS_CODEC_JP_CATALOG_URL` | URL template of the CKAN `package_search` for a municipality's registry maps, with `{code}` |
