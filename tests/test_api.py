import asyncio
import re
import shutil
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx2 import Response

from address_codec_jp import (
    AbrDataset,
    AddressCode,
    AddressCodec,
    AreaImporter,
    DatabaseCache,
    DatasetNotImportedError,
    RegistryDownloader,
    RegistryFormatError,
    RegistryImporter,
)
from address_codec_jp.frontends.api import (
    ApplicationFactory,
    CodecPool,
    DatasetCoverage,
    ServiceSettings,
)

FIXTURE_DIRECTORY: Path = Path(__file__).parent / "fixtures"
TOWN_LEVEL_FIXTURES: list[Path] = [
    FIXTURE_DIRECTORY / "mt_town_sample.csv",
    FIXTURE_DIRECTORY / "positions" / "mt_pref_pos_sample.csv",
    FIXTURE_DIRECTORY / "positions" / "mt_city_pos_sample.csv",
    FIXTURE_DIRECTORY / "positions" / "mt_town_pos_sample.csv",
]
LOT_FIXTURE_NAMES: dict[AbrDataset, str] = {
    AbrDataset.BLOCK: "mt_rsdtdsp_blk_sample.csv",
    AbrDataset.BLOCK_POSITION: "mt_rsdtdsp_blk_pos_sample.csv",
    AbrDataset.RESIDENCE: "mt_rsdtdsp_rsdt_sample.csv",
    AbrDataset.RESIDENCE_POSITION: "mt_rsdtdsp_rsdt_pos_sample.csv",
    AbrDataset.PARCEL: "mt_parcel_sample.csv",
    AbrDataset.PARCEL_POSITION: "mt_parcel_pos_sample.csv",
}
CENSUS_BOUNDARY: Path = FIXTURE_DIRECTORY / "areas" / "census_boundary_131016.zip"
REGISTRY_MAP: Path = FIXTURE_DIRECTORY / "areas" / "registry_map_113247.xml"
PUBLISHER: str = "サンプル地図株式会社"
REGISTRY_CREDIT: str = (
    "出典：「アドレス・ベース・レジストリ」（デジタル庁）"
    + "（https://www.digital.go.jp/policies/base_registry_address）"
    + "（公共データ利用規約 第1.0版 "
    + "https://www.digital.go.jp/resources/open_data/public_data_license_v1.0）"
    + "を加工してサンプル地図株式会社が作成"
)
CENSUS_CREDIT: str = (
    "出典：政府統計の総合窓口(e-Stat)（https://www.e-stat.go.jp/）"
    + "「令和2年国勢調査 町丁・字等境界データ」（総務省統計局）"
    + "を加工してサンプル地図株式会社が作成"
)
PARCEL_MASTER_CREDIT: str = (
    "出典：「登記所備付地図データ 入間郡三芳町」（法務省）"
    + "（https://www.geospatial.jp/ckan/dataset?q=11324）を参照元とする"
    + "「アドレス・ベース・レジストリ 地番マスター」（デジタル庁）"
    + "（https://www.digital.go.jp/policies/base_registry_address）"
    + "を加工してサンプル地図株式会社が作成"
)
REGISTRY_MAP_CREDIT: re.Pattern[str] = re.compile(
    "出典：「登記所備付地図データ 入間郡三芳町」（法務省）"
    + r"（https://www\.geospatial\.jp/ckan/dataset\?q=11324）"
    + r"（\d{4}年\d{1,2}月\d{1,2}日に利用）を加工してサンプル地図株式会社が作成"
)


def build_cache(
    directory: Path, *, is_lot_included: bool, is_parcel_map_included: bool = False
) -> Path:
    """Build a cache of the sample towns, the lots and boundaries of Chiyoda, and maps."""
    directory.mkdir(parents=True)
    database_path = DatabaseCache.default(directory=directory).path
    archives = directory.parent / f"{directory.name}_archives"
    archives.mkdir()
    lot_archives: list[Path] = []
    if is_lot_included:
        for target in RegistryDownloader().plan_lots(["131016"]):
            archive_path = archives / target.file_name
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.write(
                    FIXTURE_DIRECTORY / "positions" / LOT_FIXTURE_NAMES[target.dataset], "data.csv"
                )
            lot_archives.append(archive_path)
    with RegistryImporter.open(database_path) as importer:
        _ = importer.import_files([*TOWN_LEVEL_FIXTURES, *lot_archives])
    with AreaImporter.open(database_path) as area_importer:
        _ = area_importer.import_file(CENSUS_BOUNDARY, "131016")
        if is_parcel_map_included:
            _ = area_importer.import_file(REGISTRY_MAP, "113247")
    return directory


def read_object(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return cast(dict[str, object], value)


def read_list(value: object) -> list[object]:
    assert isinstance(value, list)
    return cast(list[object], value)


def body_of(response: Response) -> dict[str, object]:
    return read_object(cast(object, response.json()))


@pytest.fixture
def cache_directory(tmp_path: Path) -> Path:
    """Cache directory prepared for Chiyoda."""
    return build_cache(tmp_path / "cache", is_lot_included=True)


def open_client(
    cache_directory: Path,
    *,
    is_coverage_required: bool = True,
    is_server_exception_raised: bool = True,
) -> TestClient:
    settings = ServiceSettings(
        publisher=PUBLISHER,
        cache_directory=cache_directory,
        thread_count=2,
        max_batch_size=3,
        is_coverage_required=is_coverage_required,
    )
    application: FastAPI = ApplicationFactory(settings).create()
    return TestClient(application, raise_server_exceptions=is_server_exception_raised)


@pytest.fixture
def client(cache_directory: Path) -> Iterator[TestClient]:
    """Client of the application on the prepared cache."""
    with open_client(cache_directory) as test_client:
        yield test_client


def test_encode_returns_the_code_and_the_credit(client: TestClient) -> None:
    response = client.get("/v1/codes", params={"address": "千代田区丸の内1-2-3 丸ビル"})
    assert response.status_code == 200
    assert body_of(response) == {
        "input": "千代田区丸の内1-2-3 丸ビル",
        "code": "131016-0011001-2-3",
        "level": "RESIDENCE",
        "remainder": "丸ビル",
        "town_name_tier": "EXACT",
        "attribution": [REGISTRY_CREDIT],
    }


def test_decode_takes_format_options(client: TestClient) -> None:
    response = client.get(
        "/v1/codes/131016-0011001-2-3", params={"numeral": "kanji", "prefecture": "false"}
    )
    assert response.status_code == 200
    assert body_of(response)["address"] == "千代田区丸の内一丁目二番三号"


def test_locate_tells_whether_the_point_is_exact(client: TestClient) -> None:
    exact = body_of(client.get("/v1/locations", params={"address": "千代田区丸の内1-2-3"}))
    assert (exact["level"], exact["is_exact"]) == ("RESIDENCE", True)
    by_code = client.get("/v1/codes/131016-0011001-2-3/location", params={"crs": "wgs84"})
    assert body_of(by_code)["crs"] == "EPSG:4326"


def test_nearest_and_postal_code(client: TestClient) -> None:
    nearest = body_of(client.get("/v1/nearest", params={"coordinate": "35.682456,139.765123"}))
    assert nearest["code"] == "131016-0011001-2-3"
    towns = read_list(body_of(client.get("/v1/postal-codes/100-0005"))["towns"])
    assert {"code": "131016-0011001", "address": "東京都千代田区丸の内1丁目"} in towns


def test_area_writes_its_geometry_unless_disabled(client: TestClient) -> None:
    area = body_of(client.get("/v1/areas", params={"address": "千代田区丸の内1-2-3"}))
    geometry = read_object(area["geometry"])
    assert (area["located_code"], area["is_exact"]) == ("131016-0011001", False)
    assert geometry["type"] == "MultiPolygon"
    assert area["attribution"] == [REGISTRY_CREDIT, CENSUS_CREDIT]
    without = body_of(client.get("/v1/codes/131016-0011001/area", params={"geometry": "false"}))
    assert "geometry" not in without


def test_areas_at_omits_geometries_by_default(client: TestClient) -> None:
    response = body_of(client.get("/v1/areas-at", params={"coordinate": "35.6822,139.7660"}))
    areas = [read_object(area) for area in read_list(response["areas"])]
    assert [area["code"] for area in areas] == ["131016-0011001"]
    assert "geometry" not in areas[0]


def test_unprepared_municipality_is_rejected(client: TestClient) -> None:
    lots = client.get("/v1/locations", params={"address": "三芳町竹間沢123-4"})
    assert lots.status_code == 503
    assert body_of(lots)["error_type"] == "DatasetNotImportedError"
    town = client.get("/v1/locations", params={"address": "三芳町竹間沢"})
    assert body_of(town)["is_exact"]
    assert client.get("/v1/areas", params={"address": "三芳町竹間沢"}).status_code == 503


def test_unprepared_municipality_falls_back_without_coverage(tmp_path: Path) -> None:
    town_level = build_cache(tmp_path / "town_level", is_lot_included=False)
    with open_client(town_level, is_coverage_required=False) as client:
        location = body_of(client.get("/v1/locations", params={"address": "千代田区丸の内1-2-3"}))
    assert (location["level"], location["is_exact"]) == ("TOWN", False)


@pytest.mark.parametrize(
    ("path", "params", "status", "error_type"),
    [
        ("/v1/codes", {"address": "府中市"}, 409, "AmbiguousAddressError"),
        ("/v1/codes/131016-9999999", {}, 404, "AddressNotFoundError"),
        ("/v1/codes/abc", {}, 400, "InvalidRequestError"),
        ("/v1/codes", {"address": " "}, 400, "InvalidRequestError"),
        ("/v1/codes/131016-0011001", {"numeral": "roman"}, 400, "InvalidRequestError"),
        ("/v1/locations", {"address": "千代田区", "crs": "mercator"}, 400, "InvalidRequestError"),
        ("/v1/nearest", {"coordinate": "north"}, 400, "InvalidRequestError"),
        ("/v1/postal-codes/abc", {}, 400, "InvalidRequestError"),
    ],
)
def test_errors_map_to_statuses(
    client: TestClient, path: str, params: dict[str, str], status: int, error_type: str
) -> None:
    response = client.get(path, params=params)
    assert response.status_code == status
    assert body_of(response)["error_type"] == error_type


@pytest.mark.parametrize(
    "error", [RegistryFormatError("Corrupt row in /var/lib/addresses."), ValueError("Bug.")]
)
def test_server_faults_hide_their_detail(
    cache_directory: Path, monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    def fail(_: AddressCodec, address: str, *, is_lot_verified: bool = False) -> AddressCode:
        raise error

    monkeypatch.setattr(AddressCodec, "encode", fail)
    with open_client(cache_directory, is_server_exception_raised=False) as client:
        single = client.get("/v1/locations", params={"address": "千代田区"})
        batch = client.post("/v1/batch", json={"operation": "locate", "inputs": ["千代田区"]})
    for response in (single, batch):
        assert response.status_code == 500
        assert body_of(response) == ApplicationFactory.INTERNAL_ERROR_BODY


def test_ambiguous_address_lists_candidates(client: TestClient) -> None:
    assert body_of(client.get("/v1/codes", params={"address": "府中市"}))["candidates"] == [
        "132063",
        "342084",
    ]


def test_batch_reports_each_input(client: TestClient) -> None:
    response = client.post(
        "/v1/batch",
        json={
            "operation": "locate",
            "inputs": ["千代田区丸の内1-2-3", "府中市", "三芳町竹間沢123-4"],
        },
    )
    assert response.status_code == 200
    results = [read_object(result) for result in read_list(body_of(response)["results"])]
    assert results[0]["located_code"] == "131016-0011001-2-3"
    assert [result.get("status") for result in results] == [None, 409, 503]


def test_batch_takes_nested_format_options(client: TestClient) -> None:
    response = client.post(
        "/v1/batch",
        json={"operation": "decode", "inputs": ["131016-0011001"], "format": {"kana": True}},
    )
    result = read_object(read_list(body_of(response)["results"])[0])
    assert str(result["address"]).startswith("トウキョウト")


@pytest.mark.parametrize(
    "body",
    [
        {"operation": "encode", "inputs": ["東京都", "東京都", "東京都", "東京都"]},
        {"operation": "translate", "inputs": []},
    ],
)
def test_invalid_batch_is_rejected(client: TestClient, body: dict[str, object]) -> None:
    assert client.post("/v1/batch", json=body).status_code == 400


def test_health_reports_the_prepared_municipalities(client: TestClient) -> None:
    assert body_of(client.get("/health")) == {
        "status": "ok",
        "lot_municipality_count": 1,
        "boundary_municipality_count": 1,
        "imported_dataset_count": len(TOWN_LEVEL_FIXTURES) + len(LOT_FIXTURE_NAMES),
    }


def test_application_requires_a_built_cache(tmp_path: Path) -> None:
    with pytest.raises(DatasetNotImportedError):
        _ = ApplicationFactory(
            ServiceSettings(publisher=PUBLISHER, cache_directory=tmp_path)
        ).create()


def identify(codec: AddressCodec, coverage: DatasetCoverage) -> tuple[int, frozenset[str]]:
    return id(codec), coverage.lot_municipality_codes


def test_pool_reopens_a_replaced_database(cache_directory: Path, tmp_path: Path) -> None:
    pool = CodecPool(cache_directory, thread_count=1)
    first_codec, first_lots = asyncio.run(pool.run(identify))
    assert first_lots == frozenset({"131016"})
    assert asyncio.run(pool.run(identify)) == (first_codec, first_lots)
    replacement = build_cache(tmp_path / "replacement", is_lot_included=False)
    _ = shutil.copy(replacement / pool.database_path.name, tmp_path / "staged.sqlite3")
    _ = (tmp_path / "staged.sqlite3").replace(pool.database_path)
    second_codec, second_lots = asyncio.run(pool.run(identify))
    assert second_lots == frozenset()
    assert second_codec != first_codec
    pool.close()


def test_pool_closes_every_thread(cache_directory: Path) -> None:
    pool = CodecPool(cache_directory, thread_count=3)
    _ = asyncio.run(pool.run(identify))
    pool.close()


def test_settings_are_read_from_the_environment() -> None:
    settings = ServiceSettings.from_environment(
        {
            ServiceSettings.PUBLISHER_VARIABLE: PUBLISHER,
            ServiceSettings.THREAD_COUNT_VARIABLE: "8",
            ServiceSettings.COVERAGE_VARIABLE: "False",
        }
    )
    assert (settings.publisher, settings.thread_count, settings.max_batch_size) == (
        PUBLISHER,
        8,
        1000,
    )
    assert not settings.is_coverage_required


@pytest.mark.parametrize(
    ("environment", "pattern"),
    [
        ({}, "ADDRESS_CODEC_JP_API_PUBLISHER"),
        ({ServiceSettings.PUBLISHER_VARIABLE: " "}, "ADDRESS_CODEC_JP_API_PUBLISHER"),
        (
            {
                ServiceSettings.PUBLISHER_VARIABLE: PUBLISHER,
                ServiceSettings.THREAD_COUNT_VARIABLE: "0",
            },
            "thread_count must be positive",
        ),
        (
            {
                ServiceSettings.PUBLISHER_VARIABLE: PUBLISHER,
                ServiceSettings.MAX_BATCH_SIZE_VARIABLE: "many",
            },
            "invalid literal",
        ),
        (
            {
                ServiceSettings.PUBLISHER_VARIABLE: PUBLISHER,
                ServiceSettings.COVERAGE_VARIABLE: "maybe",
            },
            "must be true or false",
        ),
    ],
)
def test_malformed_settings_are_rejected(environment: dict[str, str], pattern: str) -> None:
    with pytest.raises(ValueError, match=pattern):
        _ = ServiceSettings.from_environment(environment)


def test_parcel_points_credit_the_registry_maps(cache_directory: Path) -> None:
    with open_client(cache_directory, is_coverage_required=False) as client:
        parcel = body_of(client.get("/v1/locations", params={"address": "三芳町竹間沢123-4"}))
        residence = body_of(client.get("/v1/locations", params={"address": "千代田区丸の内1-2-3"}))
    assert parcel["attribution"] == [REGISTRY_CREDIT, PARCEL_MASTER_CREDIT]
    assert residence["attribution"] == [REGISTRY_CREDIT]


def test_parcel_shapes_credit_the_maps_and_their_date(tmp_path: Path) -> None:
    with_maps = build_cache(tmp_path / "maps", is_lot_included=True, is_parcel_map_included=True)
    with open_client(with_maps, is_coverage_required=False) as client:
        area = body_of(client.get("/v1/codes/113247-0001000-123-4/area"))
    credits = [str(credit) for credit in read_list(area["attribution"])]
    assert area["sources"] == "registry_map"
    assert credits[0] == REGISTRY_CREDIT
    assert REGISTRY_MAP_CREDIT.fullmatch(credits[1])


def test_batch_credits_every_dataset_once(cache_directory: Path) -> None:
    with open_client(cache_directory, is_coverage_required=False) as client:
        response = client.post(
            "/v1/batch",
            json={
                "operation": "locate",
                "inputs": ["三芳町竹間沢123-4", "千代田区丸の内1-2-3", "三芳町竹間沢123-4"],
            },
        )
    assert body_of(response)["attribution"] == [REGISTRY_CREDIT, PARCEL_MASTER_CREDIT]
