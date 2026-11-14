from address_codec_jp.database.storage.point_grid import PointGrid
from address_codec_jp.geometry import CoordinateBounds


def test_row_ranges_cover_every_point_in_the_bounds() -> None:
    grid = PointGrid()
    bounds = CoordinateBounds(
        south_degrees=35.6795, north_degrees=35.7012, west_degrees=139.7599, east_degrees=139.78
    )
    ranges = grid.row_ranges(bounds)
    assert len(ranges) == 4
    for latitude in (35.6795, 35.69, 35.7012):
        for longitude in (139.7599, 139.77, 139.78):
            cell = grid.cell_of(latitude, longitude)
            assert any(first <= cell <= last for first, last in ranges)
    outside = grid.cell_of(35.69, 139.79)
    assert not any(first <= outside <= last for first, last in ranges)
