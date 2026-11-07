# AddressCodecJP

## Overview

AddressCodecJP normalizes free-form Japanese addresses and converts them to and from
stable [address codes](docs/address-codes.md) anchored to the town master (町字マスター)
of the Digital Agency's [Address Base Registry](https://www.digital.go.jp/policies/base_registry_address)
(ABR). Addresses and codes are also mapped to the ABR representative points (代表点) down
to residences and land parcels, and to area shapes from the census boundaries and the
registry office maps. A coordinate is mapped back to the nearest address and to the
towns and parcels that contain it. The data is downloaded on demand into a local
[cache](docs/cache.md); see [data sources](docs/data-sources.md) for its terms.

## Installation

Requires Python 3.12+. Add the repository to the dependencies of a project:

```toml
[project]
dependencies = [
    "address-codec-jp @ git+https://github.com/ry-yoshida-dev/AddressCodecJP.git@<commit>",
]
```

The `api` extra (`address-codec-jp[api]`) adds FastAPI and uvicorn for the
[web API](docs/web-api.md). No database setup is needed; the first use downloads the
nationwide town master into the user cache directory, and
`DatabaseCache.default(progress=ProgressBarGroup())` with
[ProgressBar](https://github.com/ry-yoshida-dev/ProgressBar) shows its progress.

## Usage

```python
from geo_coordinate import GeoCoordinate

from address_codec_jp import AddressCodec, AddressFormat, NumeralStyle

with AddressCodec.open() as codec:
    code = codec.encode("東京都千代田区丸の内１丁目２番３号")
    print(code)  # 131016-0011001-2-3
    print(codec.decode(code, AddressFormat(numeral_style=NumeralStyle.KANJI)))
    # 東京都千代田区丸の内一丁目二番三号

    match = codec.match("千代田区丸の内2-4-1 丸ビル")
    print(match.code, match.remainder)  # 131016-0011002-4-1 丸ビル

    location = codec.locate("千代田区丸の内1-9-1")
    print(location.located_code, location.is_exact)  # 131016-0011001-9 False

    nearest = codec.find_nearest(GeoCoordinate.from_degrees(35.6812, 139.7671))
    print(nearest.code, f"{nearest.distance_meters:.1f}")  # 131016-0011001-9 13.5

    area = codec.find_area("千代田区丸の内1-9-1")
    print(area.shape.to_geojson()[:30])  # {"type":"MultiPolygon","coordi
```

The same queries are available on the command line; see
[command-line.md](docs/command-line.md) for the output format.

```bash
address-codec-jp encode "千代田区丸の内一の二の三"
address-codec-jp decode 131016-0011001-2-3 --numeral kanji
address-codec-jp nearest 35.6812,139.7671
address-codec-jp area "千代田区丸の内1-9-1"
address-codec-jp cache prepare --prefecture 13
```

## Development

Install all extras so that the web API tests run:

```bash
uv sync --all-extras
```

Tag a release as `v{version}` after bumping `version` in `pyproject.toml`.
