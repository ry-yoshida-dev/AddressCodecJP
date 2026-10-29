from pathlib import Path
from types import TracebackType
from typing import Self

from address_codec_jp.storage.abr_position_csv_reader import AbrPositionCsvReader
from address_codec_jp.storage.abr_town_csv_reader import AbrTownCsvReader
from address_codec_jp.storage.address_database import AddressDatabase
from address_codec_jp.storage.import_summary import ImportSummary
from address_codec_jp.storage.position_import_summary import PositionImportSummary


class RegistryImporter:
    """
    Importer of Address Base Registry datasets into an address database.

    Parameters
    ----------
    database : AddressDatabase
        Writable database. It is closed by ``close``.

    Raises
    ------
    ValueError
        If the database was opened read-only.

    Examples
    --------
    >>> with RegistryImporter.open("towns.sqlite3") as importer:  # doctest: +SKIP
    ...     summary = importer.import_town_master(Path("mt_town_all.csv.zip"))
    """

    def __init__(self, database: AddressDatabase) -> None:
        if not database.is_writable:
            raise ValueError("RegistryImporter requires a database opened for writing.")
        self._database: AddressDatabase = database

    @classmethod
    def open(cls, database_path: Path | str) -> Self:
        """
        Open an importer on a database, creating the file if needed.

        Parameters
        ----------
        database_path : Path | str
            SQLite file path, or ``":memory:"`` for an in-memory database.

        Returns
        -------
        Self
            Importer bound to the database.

        Raises
        ------
        UnsupportedDatabaseError
            If the file exists but is not a database of this version of the library.
        """
        return cls(AddressDatabase.open_writable(database_path))

    @property
    def database(self) -> AddressDatabase:
        """
        Database the datasets are imported into.

        Returns
        -------
        AddressDatabase
            Writable database, e.g. to build an ``AddressCodec`` on an in-memory database.
        """
        return self._database

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying database."""
        self._database.close()

    def import_town_master(self, path: Path) -> ImportSummary:
        """
        Replace the database contents with the Address Base Registry town master.

        Oaza-level towns are added for oaza registered only by chome, so that
        addresses ending at the oaza, such as ``台東区浅草橋``, can be encoded.
        Towns of the previous import that are not in the new master are removed, together
        with their imported points and lot numbers. Abolished rows are skipped.

        Parameters
        ----------
        path : Path
            ``mt_town_all.csv`` or a ZIP archive containing it.

        Returns
        -------
        ImportSummary
            Numbers of registered and added towns and of removed position rows.

        Raises
        ------
        FileNotFoundError
            If the file does not exist.
        RegistryFormatError
            If the file is malformed. The previous contents are kept in that case.
        """
        replacement = self._database.towns.replace_all(AbrTownCsvReader().read(path))
        removed_position_count = self._database.positions.remove_orphans()
        return ImportSummary(
            registered_count=replacement.registered_count,
            complemented_count=replacement.complemented_count,
            removed_position_count=removed_position_count,
        )

    def import_positions(self, path: Path) -> PositionImportSummary:
        """
        Add one position-related dataset of the Address Base Registry to the database.

        Accepted are the position extensions of the prefecture, municipality, town,
        block, residence, and parcel masters, and the block, residence, and parcel
        masters that map lot numbers to the identifiers of the extensions. A lot is
        located only when both its master and its extension are imported, in any order.
        Rows with the same identifiers as earlier imports are replaced, and lots that a
        master marks abolished are removed.

        Parameters
        ----------
        path : Path
            Registry CSV file or its ZIP archive, e.g. ``mt_town_pos_pref13.csv.zip``.

        Returns
        -------
        PositionImportSummary
            Dataset of the file and numbers of stored rows and removed lots.

        Raises
        ------
        FileNotFoundError
            If the file does not exist.
        RegistryFormatError
            If the file is not a position-related dataset or is malformed. Nothing is
            stored in that case.
        """
        reader = AbrPositionCsvReader()
        dataset = reader.detect(path)
        changes = self._database.positions.save_all(reader.read(path))
        return PositionImportSummary(
            dataset=dataset,
            stored_count=changes.stored_count,
            removed_count=changes.removed_count,
        )
