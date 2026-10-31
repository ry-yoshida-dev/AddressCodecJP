from collections.abc import Iterable

import pytest
from geo_coordinate import GeoCoordinate, GeodeticCrs

from address_codec_jp import (
    AddressCodec,
    DatasetNotImportedError,
    PositionNotFoundError,
)
from address_codec_jp.frontends.api import (
    CoverageGuard,
    DatasetCoverage,
    InputInterpreter,
    InvalidRequestError,
)
from address_codec_jp.frontends.query import (
    DirectInterpreter,
    PassThroughGuard,
    QueryOperation,
    QueryOptions,
    QueryRunner,
)

NEAR_LOT: str = "35.6830,139.7660"
NEAR_TOWN: str = "35.6795,139.7641"


def coverage_of(
    lot_codes: Iterable[str] = (), boundary_codes: Iterable[str] = ()
) -> DatasetCoverage:
    return DatasetCoverage(frozenset(lot_codes), frozenset(boundary_codes), frozenset(), {})


def covered_runner(codec: AddressCodec, coverage: DatasetCoverage) -> QueryRunner:
    return QueryRunner(codec, InputInterpreter(), CoverageGuard(codec, coverage))


def nearby_lots(codec: AddressCodec, coordinate_text: str, max_distance: float) -> set[str]:
    latitude, longitude = (float(part) for part in coordinate_text.split(","))
    coordinate = GeoCoordinate.from_degrees(latitude, longitude)
    return codec.list_nearby_municipalities(coordinate, GeodeticCrs.JGD2011, max_distance)


def test_located_lot_requires_the_lots_of_its_municipality(located_codec: AddressCodec) -> None:
    rejecting = covered_runner(located_codec, coverage_of())
    with pytest.raises(DatasetNotImportedError, match="131016"):
        _ = rejecting.run(QueryOperation.LOCATE_CODE, "131016-0011001-2-3", QueryOptions())
    town = rejecting.run(QueryOperation.LOCATE_CODE, "131016-0011001", QueryOptions())
    assert town.lot_code is not None
    assert not town.lot_code.is_lot
    accepting = covered_runner(located_codec, coverage_of({"131016"}))
    lot = accepting.run(QueryOperation.LOCATE_CODE, "131016-0011001-2-3", QueryOptions())
    assert lot.fields["located_code"] == "131016-0011001-2-3"


def test_only_a_verified_encode_requires_lots(located_codec: AddressCodec) -> None:
    runner = covered_runner(located_codec, coverage_of())
    unverified = runner.run(QueryOperation.ENCODE, "千代田区丸の内1-2-3", QueryOptions())
    assert unverified.lot_code is None
    with pytest.raises(DatasetNotImportedError, match="131016"):
        _ = runner.run(
            QueryOperation.ENCODE, "千代田区丸の内1-2-3", QueryOptions(is_lot_verified=True)
        )


def test_exact_nearest_lot_needs_no_neighbouring_lots(located_codec: AddressCodec) -> None:
    runner = covered_runner(located_codec, coverage_of())
    record = runner.run(QueryOperation.NEAREST, "35.682456,139.765123", QueryOptions())
    assert record.fields["code"] == "131016-0011001-2-3"


def test_nearest_lot_requires_every_municipality_that_may_be_nearer(
    located_codec: AddressCodec,
) -> None:
    with pytest.raises(DatasetNotImportedError, match="131067"):
        _ = covered_runner(located_codec, coverage_of({"131016"})).run(
            QueryOperation.NEAREST, NEAR_LOT, QueryOptions()
        )
    nearby = nearby_lots(located_codec, NEAR_LOT, AddressCodec.DEFAULT_MAX_DISTANCE_METERS)
    record = covered_runner(located_codec, coverage_of(nearby)).run(
        QueryOperation.NEAREST, NEAR_LOT, QueryOptions()
    )
    assert record.lot_code is not None
    assert record.lot_code.is_lot


def test_nearest_town_requires_the_lots_within_the_largest_distance(
    located_codec: AddressCodec,
) -> None:
    options = QueryOptions(max_distance_meters=100.0)
    with pytest.raises(DatasetNotImportedError):
        _ = covered_runner(located_codec, coverage_of()).run(
            QueryOperation.NEAREST, NEAR_TOWN, options
        )
    nearby = nearby_lots(located_codec, NEAR_TOWN, options.max_distance_meters)
    record = covered_runner(located_codec, coverage_of(nearby)).run(
        QueryOperation.NEAREST, NEAR_TOWN, options
    )
    assert record.fields["code"] == "131016-0011002"
    assert record.lot_code is not None
    assert not record.lot_code.is_lot


def test_missing_nearest_blames_unprepared_lots_before_distance(
    located_codec: AddressCodec,
) -> None:
    options = QueryOptions(max_distance_meters=30.0)
    with pytest.raises(DatasetNotImportedError):
        _ = covered_runner(located_codec, coverage_of()).run(
            QueryOperation.NEAREST, NEAR_TOWN, options
        )
    nearby = nearby_lots(located_codec, NEAR_TOWN, options.max_distance_meters)
    with pytest.raises(PositionNotFoundError, match="within 30"):
        _ = covered_runner(located_codec, coverage_of(nearby)).run(
            QueryOperation.NEAREST, NEAR_TOWN, options
        )
    with pytest.raises(PositionNotFoundError):
        _ = covered_runner(located_codec, coverage_of()).run(
            QueryOperation.NEAREST, "35.0,135.0", QueryOptions()
        )


def test_area_requires_the_boundaries_of_its_municipality(located_codec: AddressCodec) -> None:
    with pytest.raises(DatasetNotImportedError, match="Town boundaries"):
        _ = covered_runner(located_codec, coverage_of()).run(
            QueryOperation.AREA_CODE, "131016-0011001", QueryOptions()
        )


def test_pass_through_guard_admits_unprepared_lots(located_codec: AddressCodec) -> None:
    runner = QueryRunner(located_codec, InputInterpreter(), PassThroughGuard())
    record = runner.run(QueryOperation.NEAREST, NEAR_LOT, QueryOptions())
    assert record.fields["code"] == "131016-0011001-2-3"


def test_interpreter_decides_how_malformed_input_is_reported(codec: AddressCodec) -> None:
    direct = QueryRunner(codec, DirectInterpreter(), PassThroughGuard())
    request = QueryRunner(codec, InputInterpreter(), PassThroughGuard())
    with pytest.raises(ValueError, match="Invalid address code") as direct_error:
        _ = direct.run(QueryOperation.DECODE, "abc", QueryOptions())
    assert not isinstance(direct_error.value, InvalidRequestError)
    with pytest.raises(InvalidRequestError, match="Invalid address code"):
        _ = request.run(QueryOperation.DECODE, "abc", QueryOptions())


def test_records_compare_by_their_answer(codec: AddressCodec) -> None:
    runner = QueryRunner(codec, DirectInterpreter(), PassThroughGuard())
    first = runner.run(QueryOperation.DECODE, "131016-0011001", QueryOptions())
    second = runner.run(QueryOperation.DECODE, "131016-0011001", QueryOptions())
    assert first == second
    assert "build_rows" not in repr(first)
    assert first.build_rows() == [["東京都千代田区丸の内1丁目"]]
