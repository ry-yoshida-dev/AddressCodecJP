import sqlite3
from pathlib import Path

import pytest

from address_codec_jp import AddressCodec, PositionLevel
from address_codec_jp.storage import AbrTownCsvReader

HEADER: str = (
    "lg_code,machiaza_id,pref,county,city,ward,oaza_cho,chome,koaza,"
    + "pref_kana,county_kana,city_kana,ward_kana,oaza_cho_kana,chome_kana,koaza_kana,"
    + "post_code,ablt_date\n"
)
EMPTY_TRAILING_COLUMNS: str = ",,,,,,,,,"


def write_csv(path: Path, rows: list[str]) -> Path:
    """Write a minimal town master CSV whose rows leave kana, postal code, and abolition empty."""
    _ = path.write_text(
        HEADER + "".join(f"{row}{EMPTY_TRAILING_COLUMNS}\n" for row in rows), encoding="utf-8"
    )
    return path


def test_open_rejects_missing_database(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        _ = AddressCodec.open(tmp_path / "typo.sqlite3")
    assert not (tmp_path / "typo.sqlite3").exists()


def test_encode_on_empty_database_fails_clearly() -> None:
    with AddressCodec.create(":memory:") as codec, pytest.raises(RuntimeError):
        _ = codec.encode("東京都")


def test_reimport_replaces_previous_towns(tmp_path: Path) -> None:
    old_master = write_csv(
        tmp_path / "old.csv", ["131016,0001001,東京都,,千代田区,,丸の内,一丁目,"]
    )
    new_master = write_csv(tmp_path / "new.csv", ["131032,0005006,東京都,,港区,,六本木,六丁目,"])
    with AddressCodec.create(":memory:") as codec:
        _ = codec.import_town_master(old_master)
        summary = codec.import_town_master(new_master)
        assert (summary.registered_count, summary.complemented_count) == (1, 1)
        with pytest.raises(KeyError):
            _ = codec.decode("131016-0001001")
        assert codec.decode("131032-0005006") == "東京都港区六本木6丁目"


@pytest.mark.parametrize(
    "row",
    [
        "131017,0001001,東京都,,千代田区,,丸の内,一丁目,",
        "131016,00010x1,東京都,,千代田区,,丸の内,一丁目,",
        "131016,0001001,東京都,,千代田区",
    ],
)
def test_reader_rejects_malformed_rows(tmp_path: Path, row: str) -> None:
    master = write_csv(tmp_path / "bad.csv", [row])
    with pytest.raises(ValueError):
        _ = list(AbrTownCsvReader().read(master))


def test_failed_import_keeps_previous_towns(tmp_path: Path) -> None:
    good_master = write_csv(
        tmp_path / "good.csv", ["131016,0001001,東京都,,千代田区,,丸の内,一丁目,"]
    )
    bad_master = write_csv(
        tmp_path / "bad.csv",
        [
            "131032,0005006,東京都,,港区,,六本木,六丁目,",
            "131017,0001001,東京都,,千代田区,,丸の内,一丁目,",
        ],
    )
    with AddressCodec.create(":memory:") as codec:
        _ = codec.import_town_master(good_master)
        with pytest.raises(ValueError):
            _ = codec.import_town_master(bad_master)
        assert codec.decode("131016-0001001") == "東京都千代田区丸の内1丁目"


def test_identical_duplicate_rows_are_stored_once(tmp_path: Path) -> None:
    row = "131016,0001001,東京都,,千代田区,,丸の内,一丁目,"
    master = write_csv(tmp_path / "duplicate.csv", [row, row])
    with AddressCodec.create(":memory:") as codec:
        summary = codec.import_town_master(master)
        assert summary.registered_count == 1


def test_conflicting_duplicate_rows_are_rejected(tmp_path: Path) -> None:
    master = write_csv(
        tmp_path / "conflict.csv",
        [
            "131016,0001001,東京都,,千代田区,,丸の内,一丁目,",
            "131016,0001001,東京都,,千代田区,,丸の内,二丁目,",
        ],
    )
    with AddressCodec.create(":memory:") as codec, pytest.raises(ValueError):
        _ = codec.import_town_master(master)


def test_open_is_read_only(tmp_path: Path) -> None:
    master = write_csv(tmp_path / "master.csv", ["131016,0001001,東京都,,千代田区,,丸の内,一丁目,"])
    database = tmp_path / "towns.sqlite3"
    with AddressCodec.create(database) as codec:
        _ = codec.import_town_master(master)
    with AddressCodec.open(database) as codec:
        assert codec.decode("130001") == "東京都"
        with pytest.raises(sqlite3.OperationalError):
            _ = codec.import_town_master(master)


def test_open_rejects_database_without_towns(tmp_path: Path) -> None:
    database = tmp_path / "other.sqlite3"
    sqlite3.connect(database).close()
    with pytest.raises(ValueError):
        _ = AddressCodec.open(database)


def test_abolished_towns_are_skipped(tmp_path: Path) -> None:
    master = tmp_path / "master.csv"
    _ = master.write_text(
        HEADER
        + "131016,0001001,東京都,,千代田区,,丸の内,一丁目,,,,,,,,,,\n"
        + "131016,0001002,東京都,,千代田区,,丸の内,二丁目,,,,,,,,,,2020-04-01\n",
        encoding="utf-8",
    )
    assert [town.machiaza_id for town in AbrTownCsvReader().read(master)] == ["0001001"]


def test_town_reader_keeps_readings_and_postal_codes(tmp_path: Path) -> None:
    master = tmp_path / "master.csv"
    _ = master.write_text(
        HEADER
        + "131016,0001001,東京都,,千代田区,,丸の内,一丁目,,"
        + "トウキョウト,,チヨダク,,マルノウチ,１チョウメ,,1000013;1000005,\n",
        encoding="utf-8",
    )
    town = next(AbrTownCsvReader().read(master))
    assert (town.oaza_kana, town.chome_kana) == ("マルノウチ", "１チョウメ")
    assert town.postal_codes == ("1000005", "1000013")
    assert town.municipality.prefecture.kana == "トウキョウト"


def test_reimport_removes_orphaned_positions(located_codec: AddressCodec, tmp_path: Path) -> None:
    master = write_csv(tmp_path / "new.csv", ["131016,0001001,東京都,,千代田区,,丸の内,一丁目,"])
    summary = located_codec.import_town_master(master)
    assert summary.removed_position_count > 0
    assert located_codec.locate("千代田区丸の内1-2-3").is_exact
    assert located_codec.locate("東京都").level is PositionLevel.PREFECTURE
    assert located_codec.locate_code("113247-0001000-123-4").level is PositionLevel.PREFECTURE


def test_open_rejects_database_of_an_older_version(tmp_path: Path) -> None:
    database = tmp_path / "old.sqlite3"
    with sqlite3.connect(database) as connection:
        _ = connection.execute("CREATE TABLE towns (lg_code TEXT, machiaza_id TEXT)")
    connection.close()
    with pytest.raises(ValueError, match="older version"):
        _ = AddressCodec.open(database)


def test_import_rebuilds_database_of_an_older_version(tmp_path: Path) -> None:
    database = tmp_path / "old.sqlite3"
    with sqlite3.connect(database) as connection:
        _ = connection.execute("CREATE TABLE towns (lg_code TEXT, machiaza_id TEXT)")
    connection.close()
    master = write_csv(tmp_path / "master.csv", ["131016,0001001,東京都,,千代田区,,丸の内,一丁目,"])
    with AddressCodec.create(database) as codec:
        _ = codec.import_town_master(master)
    with AddressCodec.open(database) as codec:
        assert codec.decode("131016-0001001") == "東京都千代田区丸の内1丁目"


def test_municipality_names_must_agree(tmp_path: Path) -> None:
    master = write_csv(
        tmp_path / "conflict.csv",
        [
            "131016,0001001,東京都,,千代田区,,丸の内,一丁目,",
            "131016,0001002,東京都,,中央区,,丸の内,二丁目,",
        ],
    )
    with AddressCodec.create(":memory:") as codec, pytest.raises(ValueError, match="131016"):
        _ = codec.import_town_master(master)
