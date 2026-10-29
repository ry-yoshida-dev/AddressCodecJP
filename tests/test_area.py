import json
import zipfile
from pathlib import Path

import pytest
from geo_coordinate import GeoCoordinate

from address_codec_jp import (
    AddressCode,
    AddressCodec,
    AddressDatabase,
    AddressLevel,
    AreaImport,
    AreaImporter,
    AreaNotFoundError,
    AreaShape,
    AreaSource,
    BoundaryDownloader,
    BoundaryFormatError,
    DatabaseCache,
    DatasetNotImportedError,
    RegistryDownloader,
    RegistryDownloadError,
    RegistryImporter,
)
from address_codec_jp.datasets.boundaries import CensusBoundaryReader, RegistryMapReader
from address_codec_jp.frontends.cli import CommandLineInterface
from address_codec_jp.geometry import Polygon

FIXTURE_DIRECTORY: Path = Path(__file__).parent / "fixtures"
AREA_DIRECTORY: Path = FIXTURE_DIRECTORY / "areas"
CENSUS_BOUNDARY: Path = AREA_DIRECTORY / "census_boundary_131016.zip"
REGISTRY_MAP: Path = AREA_DIRECTORY / "registry_map_113247.xml"
LOCAL_REGISTRY_MAP: Path = AREA_DIRECTORY / "registry_map_local_113247.xml"
MARUNOUCHI_1: GeoCoordinate = GeoCoordinate.from_degrees(35.6822, 139.7660)
PARCEL_CENTER: GeoCoordinate = GeoCoordinate.from_degrees(35.8362, 139.5321)
SQUARE: Polygon = Polygon(((0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0), (0.0, 0.0)))


@pytest.fixture
def area_importer(importer: RegistryImporter) -> AreaImporter:
    """Provide an area importer on the database of ``importer``."""
    return AreaImporter(importer.database)


@pytest.fixture
def area_codec(importer: RegistryImporter, area_importer: AreaImporter) -> AddressCodec:
    """Provide a codec whose database holds the sample census boundaries and parcel map."""
    _ = area_importer.import_file(CENSUS_BOUNDARY, "131016")
    _ = area_importer.import_file(REGISTRY_MAP, "113247")
    return AddressCodec(importer.database)


def test_polygon_contains_positions_outside_its_holes() -> None:
    hole = ((0.5, 0.5), (1.0, 0.5), (1.0, 1.0), (0.5, 1.0), (0.5, 0.5))
    polygon = Polygon(SQUARE.exterior, (hole,))
    assert polygon.contains(1.5, 1.5)
    assert not polygon.contains(0.7, 0.7)
    assert not polygon.contains(3.0, 1.0)
    assert not Polygon.is_clockwise(SQUARE.exterior)


def test_polygon_rejects_open_rings() -> None:
    with pytest.raises(ValueError, match="first position"):
        _ = Polygon(((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)))


def test_area_shape_round_trips_through_bytes_and_geojson() -> None:
    shape = AreaShape((SQUARE, SQUARE))
    assert AreaShape.from_bytes(shape.to_bytes()) == shape
    ring = "[[0.0,0.0],[2.0,0.0],[2.0,2.0],[0.0,2.0],[0.0,0.0]]"
    assert shape.to_geojson() == (
        '{"type":"MultiPolygon","coordinates":[[' + ring + "],[" + ring + "]]}"
    )
    with pytest.raises(ValueError, match="truncated"):
        _ = AreaShape.from_bytes(shape.to_bytes()[:-8])


def test_census_boundary_reader_reads_named_land_areas() -> None:
    areas = CensusBoundaryReader().read(CENSUS_BOUNDARY)
    addresses = {area.address for area in areas}
    assert "東京都千代田区丸の内一丁目" in addresses
    assert len(areas) == len({area.key_code for area in areas})


def test_registry_map_reader_projects_public_coordinates_only() -> None:
    parcels = RegistryMapReader().read(REGISTRY_MAP)
    assert [parcel.lot_text for parcel in parcels] == ["１２３－４", "地区外-1"]
    assert parcels[0].shape.contains(139.5321, 35.8362)
    assert RegistryMapReader().read(LOCAL_REGISTRY_MAP) == []


def test_registry_map_reader_reads_nested_archives(tmp_path: Path) -> None:
    inner = tmp_path / "11324-0302-1.zip"
    with zipfile.ZipFile(inner, "w") as archive:
        archive.write(REGISTRY_MAP, REGISTRY_MAP.name)
        archive.write(LOCAL_REGISTRY_MAP, LOCAL_REGISTRY_MAP.name)
    outer = tmp_path / "11324-0302-2026.zip"
    with zipfile.ZipFile(outer, "w") as archive:
        archive.write(inner, inner.name)
    assert len(RegistryMapReader().read(outer)) == 2


def test_import_matches_areas_to_registered_towns(area_importer: AreaImporter) -> None:
    census_import = area_importer.import_file(CENSUS_BOUNDARY, "131016")
    assert census_import.source is AreaSource.CENSUS_BOUNDARY
    assert census_import.stored_count == 5
    assert census_import.unmatched_count > 0
    map_import = area_importer.import_file(REGISTRY_MAP, "113247")
    assert (map_import.source, map_import.stored_count, map_import.unmatched_count) == (
        AreaSource.REGISTRY_MAP,
        1,
        1,
    )


def test_import_rejects_other_files(area_importer: AreaImporter) -> None:
    with pytest.raises(BoundaryFormatError):
        _ = area_importer.import_file(FIXTURE_DIRECTORY / "mt_town_sample.csv", "131016")


def test_find_area_falls_back_to_the_town(area_codec: AddressCodec) -> None:
    area = area_codec.find_area("千代田区丸の内1-2-3")
    assert str(area.located_code) == "131016-0011001"
    assert area.level is AddressLevel.TOWN
    assert not area.is_exact
    assert area.sources == frozenset({AreaSource.CENSUS_BOUNDARY})


def test_find_area_combines_the_towns_of_an_oaza_and_a_municipality(
    area_codec: AddressCodec,
) -> None:
    oaza = area_codec.find_area("千代田区丸の内")
    assert oaza.is_exact
    assert len(oaza.shape.polygons) == 3
    municipality = area_codec.find_area_code("131016")
    assert len(municipality.shape.polygons) >= 5


def test_find_area_of_a_parcel(area_codec: AddressCodec) -> None:
    area = area_codec.find_area("三芳町竹間沢123-4")
    assert area.is_exact
    assert area.sources == frozenset({AreaSource.REGISTRY_MAP})
    assert area.shape.contains(139.5321, 35.8362)


def test_find_area_of_a_prefecture_is_not_found(area_codec: AddressCodec) -> None:
    with pytest.raises(AreaNotFoundError):
        _ = area_codec.find_area_code("130001")


def test_find_area_requires_imported_shapes(codec: AddressCodec) -> None:
    with pytest.raises(DatasetNotImportedError):
        _ = codec.find_area("千代田区丸の内1")


def test_find_areas_at_lists_towns_then_parcels(area_codec: AddressCodec) -> None:
    towns = [str(area.code) for area in area_codec.find_areas_at(MARUNOUCHI_1)]
    assert towns == ["131016-0011001"]
    assert area_codec.find_areas_at(PARCEL_CENTER) == []
    parcels = area_codec.find_areas_at(PARCEL_CENTER, is_parcel_included=True)
    assert [str(area.code) for area in parcels] == ["113247-0001000-123-4"]


@pytest.fixture
def boundary_mirror(tmp_path: Path) -> Path:
    """Build a mirror of e-Stat and the map catalog serving Chiyoda and Miyoshi."""
    root = tmp_path / "boundary_mirror"
    (root / "census").mkdir(parents=True)
    _ = (root / "census" / "13101.zip").write_bytes(CENSUS_BOUNDARY.read_bytes())
    with zipfile.ZipFile(root / "census" / "11324.zip", "w"):
        pass
    maps = root / "maps"
    maps.mkdir()
    with zipfile.ZipFile(maps / "11324-0302-2026.zip", "w") as archive:
        archive.write(REGISTRY_MAP, REGISTRY_MAP.name)
    catalog = root / "catalog"
    catalog.mkdir()
    resources = [
        {"name": "11324-0302-2025.zip", "url": (maps / "11324-0302-2025.zip").as_uri()},
        {"name": "11324-0302-2026.zip", "url": (maps / "11324-0302-2026.zip").as_uri()},
        {"name": "license.pdf", "url": (maps / "license.pdf").as_uri()},
    ]
    _ = (catalog / "11324.json").write_text(
        json.dumps({"result": {"results": [{"resources": resources}]}})
    )
    _ = (catalog / "13101.json").write_text(json.dumps({"result": {"results": []}}))
    return root


@pytest.fixture
def boundary_downloader(boundary_mirror: Path) -> BoundaryDownloader:
    """Provide a boundary downloader that reads from ``boundary_mirror``."""
    return BoundaryDownloader(
        census_url_template=boundary_mirror.as_uri() + "/census/{code}.zip",
        catalog_url_template=boundary_mirror.as_uri() + "/catalog/{code}.json",
    )


def test_boundary_downloader_skips_empty_archives(
    boundary_downloader: BoundaryDownloader, tmp_path: Path
) -> None:
    path = boundary_downloader.download_census_boundary("131016", tmp_path / "data")
    assert path == tmp_path / "data" / "census_boundary_131016.zip"
    assert boundary_downloader.download_census_boundary("113247", tmp_path / "data") is None
    assert boundary_downloader.download_census_boundary("016951", tmp_path / "data") is None


def test_boundary_downloader_picks_the_latest_map_of_each_office(
    boundary_downloader: BoundaryDownloader, tmp_path: Path
) -> None:
    urls = boundary_downloader.list_registry_map_urls("113247")
    assert [url.rsplit("/", 1)[-1] for url in urls] == ["11324-0302-2026.zip"]
    assert boundary_downloader.list_registry_map_urls("131016") == []
    paths = boundary_downloader.download_registry_maps("113247", tmp_path / "maps")
    assert [path.name for path in paths] == ["11324-0302-2026.zip"]


def test_boundary_downloader_reads_every_catalog_page(boundary_mirror: Path) -> None:
    maps = boundary_mirror / "maps"
    catalog = boundary_mirror / "catalog"
    pages = [
        {"name": "11324-0301-2024.zip", "url": (maps / "11324-0301-2024.zip").as_uri()},
        {"name": "11324-0302-2026.zip", "url": (maps / "11324-0302-2026.zip").as_uri()},
    ]
    for start, resource in enumerate(pages):
        name = "paged11324.json" if start == 0 else f"paged11324.json&start={start}"
        result = {"count": len(pages), "results": [{"resources": [resource]}]}
        _ = (catalog / name).write_text(json.dumps({"result": result}))
    _ = (catalog / "broken11324.json").write_text(json.dumps({"result": []}))
    downloader = BoundaryDownloader(catalog_url_template=catalog.as_uri() + "/paged{code}.json")
    with pytest.raises(RegistryDownloadError):
        _ = BoundaryDownloader(
            catalog_url_template=catalog.as_uri() + "/broken{code}.json"
        ).list_registry_map_urls("113247")
    urls = downloader.list_registry_map_urls("113247")
    assert [url.rsplit("/", 1)[-1] for url in urls] == [
        "11324-0301-2024.zip",
        "11324-0302-2026.zip",
    ]


def test_cache_adds_areas_on_demand(
    boundary_downloader: BoundaryDownloader, tmp_path: Path
) -> None:
    cache = DatabaseCache(tmp_path / "cache", RegistryDownloader(), boundary_downloader)
    cache.path.parent.mkdir()
    with RegistryImporter.open(cache.path) as importer:
        _ = importer.import_file(FIXTURE_DIRECTORY / "mt_town_sample.csv")
    with AddressCodec(AddressDatabase.open_read_only(cache.path), cache) as codec:
        assert codec.find_area("千代田区丸の内1-2-3").level is AddressLevel.TOWN
        parcel = codec.find_area_code(AddressCode.parse("113247-0001000-123-4"))
        assert parcel.is_exact
    sources = {(area_import.source, area_import.lg_code) for area_import in imported_areas(cache)}
    assert sources == {
        (AreaSource.CENSUS_BOUNDARY, "131016"),
        (AreaSource.REGISTRY_MAP, "113247"),
    }
    cache.ensure_areas(["131016", "113247"], is_parcel_included=False)
    assert len(imported_areas(cache)) == 2


def imported_areas(cache: DatabaseCache) -> list[AreaImport]:
    with AddressDatabase.open_read_only(cache.path) as database:
        return database.areas.list_imports()


def test_area_commands(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    database = str(tmp_path / "towns.sqlite3")
    cli = CommandLineInterface()
    town_master = str(FIXTURE_DIRECTORY / "mt_town_sample.csv")
    assert cli.run(["--database", database, "import", town_master]) == 0
    arguments = ["--database", database, "import-area", "--lg-code", "113247", str(REGISTRY_MAP)]
    assert cli.run(arguments) == 0
    arguments = ["--database", database, "import-area", "--lg-code", "131016", str(CENSUS_BOUNDARY)]
    assert cli.run(arguments) == 0
    _ = capsys.readouterr()
    assert cli.run(["--database", database, "area", "千代田区丸の内1-2-3"]) == 0
    fields = capsys.readouterr().out.rstrip("\n").split("\t")
    assert fields[:4] == ["131016-0011001-2-3", "131016-0011001", "TOWN", "census_boundary"]
    assert fields[4].startswith('{"type":"MultiPolygon"')
    assert cli.run(["--database", database, "area-at", "35.8362,139.5321", "--parcels"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "113247-0001000-123-4\t埼玉県入間郡三芳町竹間沢123番地4\tRESIDENCE\tregistry_map"
    ]
    assert cli.run(["--database", database, "area-at", "35.8362,139.5321"]) == 1
    assert "No imported area shape" in capsys.readouterr().err
    assert cli.run(["--database", database, "info"]) == 0
    assert "census_boundary" in capsys.readouterr().out
