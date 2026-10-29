import pytest
from geo_coordinate import GeoCoordinate, GeodeticCrs

from address_codec_jp import (
    AddressCodec,
    AddressLevel,
    DatasetNotImportedError,
    PositionNotFoundError,
)


@pytest.mark.parametrize(
    ("latitude", "longitude", "code", "level"),
    [
        (35.682456, 139.765123, "131016-0001001-2-3", AddressLevel.RESIDENCE),
        (35.68201, 139.76501, "131016-0001001-2", AddressLevel.BLOCK),
        (35.6795, 139.7641, "131016-0001001-2", AddressLevel.BLOCK),
        (35.8362, 139.5321, "113247-0001000-123-4", AddressLevel.RESIDENCE),
        (35.836, 139.532, "113247-0001000-123", AddressLevel.BLOCK),
        (35.6971, 139.7851, "131067-0001001", AddressLevel.TOWN),
    ],
)
def test_nearest_point_is_found(
    located_codec: AddressCodec, latitude: float, longitude: float, code: str, level: AddressLevel
) -> None:
    nearest = located_codec.find_nearest(GeoCoordinate.from_degrees(latitude, longitude))
    assert str(nearest.code) == code
    assert nearest.location.level is level
    assert nearest.location.is_exact
    assert 0.0 <= nearest.distance_meters < 1000.0


def test_exact_point_has_zero_distance(located_codec: AddressCodec) -> None:
    nearest = located_codec.find_nearest(GeoCoordinate.from_degrees(35.682456, 139.765123))
    assert nearest.distance_meters == pytest.approx(0.0, abs=1e-6)
    assert nearest.location.latitude_degrees == pytest.approx(35.682456)


def test_abolished_block_is_not_returned(located_codec: AddressCodec) -> None:
    nearest = located_codec.find_nearest(GeoCoordinate.from_degrees(35.683, 139.766))
    assert str(nearest.code) != "131016-0001001-5"


def test_point_is_returned_on_the_requested_datum(located_codec: AddressCodec) -> None:
    coordinate = GeoCoordinate.from_degrees(35.682456, 139.765123)
    nearest = located_codec.find_nearest(coordinate, GeodeticCrs.WGS84)
    assert nearest.location.crs is GeodeticCrs.WGS84
    assert str(nearest.code) == "131016-0001001-2-3"


def test_town_is_returned_when_no_lot_is_within_the_limit(located_codec: AddressCodec) -> None:
    coordinate = GeoCoordinate.from_degrees(35.6795, 139.7641)
    nearest = located_codec.find_nearest(coordinate, max_distance_meters=100.0)
    assert str(nearest.code) == "131016-0001002"
    assert nearest.distance_meters == pytest.approx(56.0, abs=1.0)


def test_distance_limit_is_respected(located_codec: AddressCodec) -> None:
    coordinate = GeoCoordinate.from_degrees(35.6795, 139.7641)
    with pytest.raises(PositionNotFoundError, match="within 30"):
        _ = located_codec.find_nearest(coordinate, max_distance_meters=30.0)


def test_far_away_coordinate_is_rejected(located_codec: AddressCodec) -> None:
    with pytest.raises(LookupError):
        _ = located_codec.find_nearest(GeoCoordinate.from_degrees(35.0, 135.0))


def test_non_positive_distance_is_rejected(located_codec: AddressCodec) -> None:
    with pytest.raises(ValueError, match="positive"):
        _ = located_codec.find_nearest(
            GeoCoordinate.from_degrees(35.0, 135.0), max_distance_meters=0.0
        )


def test_nearest_without_positions_fails_clearly(codec: AddressCodec) -> None:
    with pytest.raises(DatasetNotImportedError, match="No positions"):
        _ = codec.find_nearest(GeoCoordinate.from_degrees(35.0, 135.0))
