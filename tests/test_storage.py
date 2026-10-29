import sqlite3
from pathlib import Path

import pytest

from address_codec_jp import (
    AddressCodec,
    AddressDatabase,
    AddressLevel,
    AddressNotFoundError,
    DatasetNotImportedError,
    RegistryFormatError,
    RegistryImporter,
    UnsupportedDatabaseError,
)
from address_codec_jp.storage import AbrTownCsvReader

HEADER: str = (
    "lg_code,machiaza_id,pref,county,city,ward,oaza_cho,chome,koaza,"
    + "pref_kana,county_kana,city_kana,ward_kana,oaza_cho_kana,chome_kana,koaza_kana,"
    + "post_code,ablt_date\n"
)
EMPTY_TRAILING_COLUMNS: str = ",,,,,,,,,"
MARUNOUCHI_ROW: str = "131016,0001001,東京都,,千代田区,,丸の内,一丁目,"


def write_csv(path: Path, rows: list[str]) -> Path:
    """Write a minimal town master CSV whose rows leave kana, postal code, and abolition empty."""
    _ = path.write_text(
        HEADER + "".join(f"{row}{EMPTY_TRAILING_COLUMNS}\n" for row in rows), encoding="utf-8"
    )
    return path


def build_database(tmp_path: Path) -> Path:
    """Import a one-town master into a database file."""
    database = tmp_path / "towns.sqlite3"
    with RegistryImporter.open(database) as importer:
        _ = importer.import_town_master(write_csv(tmp_path / "master.csv", [MARUNOUCHI_ROW]))
    return database


def test_open_rejects_missing_database(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        _ = AddressCodec.open(tmp_path / "typo.sqlite3")
    assert not (tmp_path / "typo.sqlite3").exists()


def test_encode_on_empty_database_fails_clearly() -> None:
    with RegistryImporter.open(":memory:") as importer, pytest.raises(DatasetNotImportedError):
        _ = AddressCodec(importer.database).encode("東京都")


def test_reimport_replaces_previous_towns(tmp_path: Path) -> None:
    old_master = write_csv(tmp_path / "old.csv", [MARUNOUCHI_ROW])
    new_master = write_csv(tmp_path / "new.csv", ["131032,0005006,東京都,,港区,,六本木,六丁目,"])
    with RegistryImporter.open(":memory:") as importer:
        _ = importer.import_town_master(old_master)
        summary = importer.import_town_master(new_master)
        assert (summary.registered_count, summary.complemented_count) == (1, 1)
        codec = AddressCodec(importer.database)
        with pytest.raises(AddressNotFoundError):
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
    with pytest.raises(RegistryFormatError, match="Row 2"):
        _ = list(AbrTownCsvReader().read(master))


def test_failed_import_keeps_previous_towns(tmp_path: Path) -> None:
    good_master = write_csv(tmp_path / "good.csv", [MARUNOUCHI_ROW])
    bad_master = write_csv(
        tmp_path / "bad.csv",
        [
            "131032,0005006,東京都,,港区,,六本木,六丁目,",
            "131017,0001001,東京都,,千代田区,,丸の内,一丁目,",
        ],
    )
    with RegistryImporter.open(":memory:") as importer:
        _ = importer.import_town_master(good_master)
        with pytest.raises(RegistryFormatError, match="Row 3"):
            _ = importer.import_town_master(bad_master)
        assert AddressCodec(importer.database).decode("131016-0001001") == (
            "東京都千代田区丸の内1丁目"
        )


def test_identical_duplicate_rows_are_stored_once(tmp_path: Path) -> None:
    master = write_csv(tmp_path / "duplicate.csv", [MARUNOUCHI_ROW, MARUNOUCHI_ROW])
    with RegistryImporter.open(":memory:") as importer:
        summary = importer.import_town_master(master)
        assert summary.registered_count == 1


def test_conflicting_duplicate_rows_are_rejected(tmp_path: Path) -> None:
    master = write_csv(
        tmp_path / "conflict.csv",
        [MARUNOUCHI_ROW, "131016,0001001,東京都,,千代田区,,丸の内,二丁目,"],
    )
    with RegistryImporter.open(":memory:") as importer, pytest.raises(RegistryFormatError):
        _ = importer.import_town_master(master)


def test_codec_opens_database_read_only(tmp_path: Path) -> None:
    database = build_database(tmp_path)
    with AddressCodec.open(database) as codec:
        assert codec.decode("130001") == "東京都"
    with pytest.raises(ValueError, match="writing"):
        _ = RegistryImporter(AddressDatabase.open_read_only(database))


def test_importer_adds_to_existing_database(tmp_path: Path) -> None:
    database = build_database(tmp_path)
    with RegistryImporter.open(database) as importer:
        _ = importer.import_town_master(
            write_csv(tmp_path / "new.csv", ["131032,0005006,東京都,,港区,,六本木,六丁目,"])
        )
    with AddressCodec.open(database) as codec:
        assert codec.decode("131032-0005006") == "東京都港区六本木6丁目"


@pytest.mark.parametrize("is_table_created", [False, True])
def test_open_rejects_foreign_sqlite_database(tmp_path: Path, is_table_created: bool) -> None:
    database = tmp_path / "other.sqlite3"
    with sqlite3.connect(database) as connection:
        if is_table_created:
            _ = connection.execute("CREATE TABLE towns (lg_code TEXT, machiaza_id TEXT)")
    connection.close()
    with pytest.raises(UnsupportedDatabaseError, match="not an AddressCodecJP database"):
        _ = AddressCodec.open(database)
    if is_table_created:
        with pytest.raises(UnsupportedDatabaseError):
            _ = RegistryImporter.open(database)


def test_open_rejects_file_that_is_not_sqlite(tmp_path: Path) -> None:
    database = tmp_path / "notes.txt"
    _ = database.write_text("not a database " * 100, encoding="utf-8")
    with pytest.raises(UnsupportedDatabaseError, match="not an SQLite database"):
        _ = AddressCodec.open(database)


def test_open_rejects_database_of_another_schema_version(tmp_path: Path) -> None:
    database = build_database(tmp_path)
    with sqlite3.connect(database) as connection:
        _ = connection.execute("PRAGMA user_version = 0")
    connection.close()
    with pytest.raises(UnsupportedDatabaseError, match="schema version 0"):
        _ = AddressCodec.open(database)
    with pytest.raises(UnsupportedDatabaseError, match="schema version 0"):
        _ = RegistryImporter.open(database)


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


def test_reimport_removes_orphaned_positions(
    importer: RegistryImporter, located_codec: AddressCodec, tmp_path: Path
) -> None:
    assert located_codec.locate("千代田区丸の内1-2-3").is_exact
    master = write_csv(tmp_path / "new.csv", [MARUNOUCHI_ROW])
    summary = importer.import_town_master(master)
    assert summary.removed_position_count > 0
    codec = AddressCodec(importer.database)
    assert codec.locate("千代田区丸の内1-2-3").is_exact
    assert codec.locate("東京都").level is AddressLevel.PREFECTURE
    assert codec.locate_code("113247-0001000-123-4").level is AddressLevel.PREFECTURE


def test_municipality_names_must_agree(tmp_path: Path) -> None:
    master = write_csv(
        tmp_path / "conflict.csv",
        [
            "131016,0001001,東京都,,千代田区,,丸の内,一丁目,",
            "131016,0001002,東京都,,中央区,,丸の内,二丁目,",
        ],
    )
    with (
        RegistryImporter.open(":memory:") as importer,
        pytest.raises(RegistryFormatError, match="131016"),
    ):
        _ = importer.import_town_master(master)
