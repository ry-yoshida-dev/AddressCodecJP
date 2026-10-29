import sqlite3
from pathlib import Path

import pytest

from address_codec_jp import AddressCodec
from address_codec_jp.storage import AbrTownCsvReader

HEADER: str = "lg_code,machiaza_id,pref,county,city,ward,oaza_cho,chome,koaza\n"


def write_csv(path: Path, rows: list[str]) -> Path:
    """Write a minimal town master CSV."""
    _ = path.write_text(HEADER + "".join(f"{row}\n" for row in rows), encoding="utf-8")
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
