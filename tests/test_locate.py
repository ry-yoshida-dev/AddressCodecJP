import zipfile
from pathlib import Path

import pytest
from geo_coordinate import GeoCoordinate, GeodeticCrs

from address_codec_jp import AddressCodec, AddressLocation, PositionLevel
from address_codec_jp.storage import (
    AbrPositionCsvReader,
    AbrPositionDataset,
    LotEntry,
    LotRemoval,
)

FIXTURE_DIRECTORY: Path = Path(__file__).parent / "fixtures"
POSITION_FIXTURES: list[Path] = sorted((FIXTURE_DIRECTORY / "positions").glob("*.csv"))


def degrees(location: AddressLocation) -> tuple[float, float]:
    """Latitude and longitude of a location in degrees."""
    return (location.latitude_degrees, location.longitude_degrees)


@pytest.mark.parametrize(
    ("address", "located_code", "level", "expected_degrees"),
    [
        (
            "千代田区丸の内1-2-3",
            "131016-0001001-2-3",
            PositionLevel.RESIDENCE,
            (35.682456, 139.765123),
        ),
        ("千代田区丸の内1-2-9", "131016-0001001-2", PositionLevel.BLOCK, (35.682, 139.765)),
        ("千代田区丸の内1-2", "131016-0001001-2", PositionLevel.BLOCK, (35.682, 139.765)),
        ("千代田区丸の内1-7", "131016-0001001", PositionLevel.TOWN, (35.68156, 139.767201)),
        ("千代田区丸の内1-5", "131016-0001001", PositionLevel.TOWN, (35.68156, 139.767201)),
        ("千代田区丸の内1-2-4", "131016-0001001-2", PositionLevel.BLOCK, (35.682, 139.765)),
        ("千代田区丸の内3丁目", "131016", PositionLevel.MUNICIPALITY, (35.694003, 139.753634)),
        ("三芳町竹間沢123-4", "113247-0001000-123-4", PositionLevel.RESIDENCE, (35.8362, 139.5321)),
        ("三芳町竹間沢123-5", "113247-0001000-123", PositionLevel.BLOCK, (35.836, 139.532)),
        ("三芳町竹間沢124-1", "113247-0001000", PositionLevel.TOWN, (35.835, 139.531)),
        ("三芳町竹間沢字東12", "113247-0001000", PositionLevel.TOWN, (35.835, 139.531)),
        ("台東区浅草橋", "131067", PositionLevel.MUNICIPALITY, (35.712607, 139.779984)),
        ("台東区浅草橋1丁目", "131067-0001001", PositionLevel.TOWN, (35.697, 139.785)),
        ("東京都", "130001", PositionLevel.PREFECTURE, (35.689568, 139.691717)),
        ("港区六本木6丁目", "130001", PositionLevel.PREFECTURE, (35.689568, 139.691717)),
    ],
)
def test_locate_falls_back_to_the_nearest_area_with_a_point(
    located_codec: AddressCodec,
    address: str,
    located_code: str,
    level: PositionLevel,
    expected_degrees: tuple[float, float],
) -> None:
    location = located_codec.locate(address)
    assert str(location.located_code) == located_code
    assert location.level is level
    assert location.crs is GeodeticCrs.JGD2011
    assert degrees(location) == pytest.approx(expected_degrees, abs=1e-6)


def test_residence_indication_town_ignores_parcels(located_codec: AddressCodec) -> None:
    location = located_codec.locate("千代田区丸の内1-2-3")
    assert location.is_exact
    assert degrees(location) != pytest.approx((35.6, 139.7), abs=1e-3)


def test_locate_code_accepts_string_and_code(located_codec: AddressCodec) -> None:
    by_text = located_codec.locate_code("131016-0001001-2-3")
    by_code = located_codec.locate_code(by_text.code)
    assert by_text.located_code == by_code.located_code
    assert by_text.coordinate == by_code.coordinate


def test_locate_on_another_datum(located_codec: AddressCodec) -> None:
    on_jgd2011 = located_codec.locate("千代田区丸の内1-2-3")
    on_tokyo = located_codec.locate("千代田区丸の内1-2-3", GeodeticCrs.TOKYO)
    assert on_tokyo.crs is GeodeticCrs.TOKYO
    shift = float(on_jgd2011.coordinate.distance_to(on_tokyo.coordinate).meter.flat[0])
    assert 300.0 < shift < 600.0


def test_import_order_does_not_matter(codec: AddressCodec) -> None:
    for path in reversed(POSITION_FIXTURES):
        _ = codec.import_positions(path)
    assert codec.locate("千代田区丸の内1-2-3").level is PositionLevel.RESIDENCE


def test_reimport_replaces_rows(located_codec: AddressCodec, tmp_path: Path) -> None:
    moved = tmp_path / "moved.csv"
    _ = moved.write_text(
        "lg_code,rep_lon,rep_lat,rep_srid\n130001,139.0,35.0,EPSG:6668\n", encoding="utf-8"
    )
    summary = located_codec.import_positions(moved)
    assert (summary.dataset, summary.stored_count) == (AbrPositionDataset.AREA_POSITION, 1)
    assert degrees(located_codec.locate("東京都")) == pytest.approx((35.0, 139.0))


def test_import_reads_zip_archives(codec: AddressCodec, tmp_path: Path) -> None:
    archive_path = tmp_path / "mt_pref_pos_all.csv.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.write(FIXTURE_DIRECTORY / "positions" / "mt_pref_pos_sample.csv", "pref.csv")
    assert codec.import_positions(archive_path).stored_count == 2
    assert codec.locate("東京都").level is PositionLevel.PREFECTURE


def test_locate_without_positions_fails_clearly(codec: AddressCodec) -> None:
    with pytest.raises(RuntimeError, match="No positions"):
        _ = codec.locate("東京都")


def test_locate_without_any_enclosing_point_raises(located_codec: AddressCodec) -> None:
    with pytest.raises(LookupError, match="No position is imported"):
        _ = located_codec.locate("広島県府中市府川町5")


def test_town_master_is_not_a_position_dataset(codec: AddressCodec) -> None:
    with pytest.raises(ValueError, match="Not a position dataset"):
        _ = codec.import_positions(FIXTURE_DIRECTORY / "mt_town_sample.csv")


def test_failed_import_stores_nothing(located_codec: AddressCodec, tmp_path: Path) -> None:
    broken = tmp_path / "broken.csv"
    _ = broken.write_text(
        "lg_code,rep_lon,rep_lat,rep_srid\n130001,139.0,35.0,EPSG:6668\n130001,139.0,35.0,EPSG:1\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        _ = located_codec.import_positions(broken)
    assert degrees(located_codec.locate("東京都")) == pytest.approx((35.689568, 139.691717))


@pytest.mark.parametrize(
    ("file_name", "dataset"),
    [
        ("mt_pref_pos_sample.csv", AbrPositionDataset.AREA_POSITION),
        ("mt_city_pos_sample.csv", AbrPositionDataset.AREA_POSITION),
        ("mt_town_pos_sample.csv", AbrPositionDataset.TOWN_POSITION),
        ("mt_rsdtdsp_blk_sample.csv", AbrPositionDataset.BLOCK),
        ("mt_rsdtdsp_blk_pos_sample.csv", AbrPositionDataset.BLOCK_POSITION),
        ("mt_rsdtdsp_rsdt_sample.csv", AbrPositionDataset.RESIDENCE),
        ("mt_rsdtdsp_rsdt_pos_sample.csv", AbrPositionDataset.RESIDENCE_POSITION),
        ("mt_parcel_sample.csv", AbrPositionDataset.PARCEL),
        ("mt_parcel_pos_sample.csv", AbrPositionDataset.PARCEL_POSITION),
    ],
)
def test_dataset_is_detected_by_header(file_name: str, dataset: AbrPositionDataset) -> None:
    assert AbrPositionCsvReader().detect(FIXTURE_DIRECTORY / "positions" / file_name) is dataset


def test_unexpressible_lots_are_skipped_and_abolished_lots_removed() -> None:
    reader = AbrPositionCsvReader()
    positions = FIXTURE_DIRECTORY / "positions"
    block_records = list(reader.read(positions / "mt_rsdtdsp_blk_sample.csv"))
    assert [type(record) for record in block_records] == [LotEntry, LotRemoval]
    assert len(list(reader.read(positions / "mt_rsdtdsp_rsdt_sample.csv"))) == 1
    assert len(list(reader.read(positions / "mt_parcel_sample.csv"))) == 4


def test_newer_master_removes_abolished_lots(located_codec: AddressCodec, tmp_path: Path) -> None:
    assert located_codec.locate("千代田区丸の内1-2").level is PositionLevel.BLOCK
    newer_master = tmp_path / "mt_rsdtdsp_blk_newer.csv"
    _ = newer_master.write_text(
        "lg_code,machiaza_id,blk_id,city,oaza_cho,chome,blk_num,ablt_date\n"
        + "131016,0001001,001,千代田区,丸の内,一丁目,2,2026-04-01\n",
        encoding="utf-8",
    )
    summary = located_codec.import_positions(newer_master)
    assert (summary.stored_count, summary.removed_count) == (0, 1)
    assert located_codec.locate("千代田区丸の内1-2").level is PositionLevel.TOWN


def test_location_coordinate_is_a_geo_coordinate(located_codec: AddressCodec) -> None:
    location = located_codec.locate("東京都")
    assert isinstance(location.coordinate, GeoCoordinate)


def test_fallback_location_is_not_exact(located_codec: AddressCodec) -> None:
    location = located_codec.locate("千代田区丸の内1-2-9")
    assert str(location.code) == "131016-0001001-2-9"
    assert not location.is_exact
