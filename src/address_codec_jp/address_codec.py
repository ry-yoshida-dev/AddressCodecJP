from pathlib import Path
from types import TracebackType
from typing import Self

from address_codec_jp.domain.address_code import AddressCode
from address_codec_jp.domain.address_level import AddressLevel
from address_codec_jp.domain.address_match import AddressMatch
from address_codec_jp.formatting.address_format import AddressFormat
from address_codec_jp.formatting.address_formatter import AddressFormatter
from address_codec_jp.matching.area_matcher import AreaMatcher
from address_codec_jp.normalization.lot_number_parser import LotNumberParser
from address_codec_jp.normalization.text_normalizer import TextNormalizer
from address_codec_jp.storage.abr_town_csv_reader import AbrTownCsvReader
from address_codec_jp.storage.import_summary import ImportSummary
from address_codec_jp.storage.town_repository import TownRepository


class AddressCodec:
    """
    Converter between free-form Japanese addresses and address codes.

    Parameters
    ----------
    repository : TownRepository
        Town dictionary used for matching and decoding.

    Examples
    --------
    >>> with AddressCodec.open("towns.sqlite3") as codec:  # doctest: +SKIP
    ...     code = codec.encode("東京都千代田区丸の内１丁目２番３号")
    ...     codec.decode(code)
    '東京都千代田区丸の内1丁目2番3号'
    """

    def __init__(self, repository: TownRepository) -> None:
        self._repository: TownRepository = repository
        self._normalizer: TextNormalizer = TextNormalizer()
        self._matcher: AreaMatcher = self._create_matcher()
        self._formatter: AddressFormatter = AddressFormatter()

    def _create_matcher(self) -> AreaMatcher:
        return AreaMatcher(self._repository, self._normalizer, LotNumberParser())

    @classmethod
    def open(cls, database_path: Path | str) -> Self:
        """
        Open a codec backed by an existing town database in read-only mode.

        Use ``create`` to import a town master.

        Parameters
        ----------
        database_path : Path | str
            SQLite file created by ``create`` and ``import_town_master``.

        Returns
        -------
        Self
            Codec bound to the database.

        Raises
        ------
        FileNotFoundError
            If the database file does not exist.
        ValueError
            If the file is an SQLite database without a town table.
        """
        return cls(TownRepository.open(database_path))

    @classmethod
    def create(cls, database_path: Path | str) -> Self:
        """
        Open a codec backed by a town database, creating the file if needed.

        Use this before ``import_town_master``.

        Parameters
        ----------
        database_path : Path | str
            SQLite file path, or ``":memory:"`` for an in-memory database.

        Returns
        -------
        Self
            Codec bound to the database.
        """
        return cls(TownRepository.create(database_path))

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
        self._repository.close()

    def import_town_master(self, path: Path) -> ImportSummary:
        """
        Replace the database contents with the Address Base Registry town master.

        Oaza-level towns are added for oaza registered only by chome, so that
        addresses ending at the oaza, such as ``台東区浅草橋``, can be encoded.
        Towns of the previous import that are not in the new master are removed.

        Parameters
        ----------
        path : Path
            ``mt_town_all.csv`` or a ZIP archive containing it.

        Returns
        -------
        ImportSummary
            Numbers of registered and added towns.

        Raises
        ------
        FileNotFoundError
            If the file does not exist.
        ValueError
            If the file is malformed. The previous contents are kept in that case.
        """
        summary = self._repository.replace_all(AbrTownCsvReader().read(path))
        self._matcher = self._create_matcher()
        return summary

    def match(self, address: str) -> AddressMatch:
        """
        Interpret a free-form address.

        Parameters
        ----------
        address : str
            Address in any common notation.

        Returns
        -------
        AddressMatch
            Matched prefecture, municipality, town, lot numbers, and unparsed remainder.
            The address may end at the prefecture, municipality, oaza, or chome.

        Raises
        ------
        ValueError
            If the address is blank.
        LookupError
            If the address does not match a registered area, or is ambiguous.
        RuntimeError
            If the database contains no towns.
        """
        normalized_address = self._normalizer.normalize(address)
        if not normalized_address:
            raise ValueError("Address must not be blank.")
        area_match = self._matcher.match(normalized_address)
        return AddressMatch(
            normalized_address=normalized_address,
            prefecture=area_match.prefecture,
            municipality=area_match.municipality,
            town=area_match.town,
            lot=area_match.lot,
            remainder=area_match.remainder,
        )

    def encode(self, address: str) -> AddressCode:
        """
        Convert an address to its address code.

        Parameters
        ----------
        address : str
            Address in any common notation.

        Returns
        -------
        AddressCode
            Code of the address at the most specific level it contains.
            Building names and room numbers are not encoded.

        Raises
        ------
        ValueError
            If the address is blank.
        LookupError
            If the address does not match a registered area.
        """
        return self.match(address).code

    def decode(self, code: AddressCode | str, address_format: AddressFormat | None = None) -> str:
        """
        Convert an address code to address text.

        Parameters
        ----------
        code : AddressCode | str
            Address code or its string form.
        address_format : AddressFormat | None
            Output format. The default format is used when omitted.

        Returns
        -------
        str
            Formatted address.

        Raises
        ------
        ValueError
            If a string code is malformed, or lot numbers are attached to an oaza that
            takes them only under a chome.
        KeyError
            If the area of the code is not registered.
        """
        address_code = code if isinstance(code, AddressCode) else AddressCode.parse(code)
        selected_format = address_format or AddressFormat()
        match address_code.level:
            case AddressLevel.PREFECTURE:
                return self._formatter.format_prefecture(
                    self._repository.get_prefecture(address_code.prefecture_code)
                )
            case AddressLevel.MUNICIPALITY:
                return self._formatter.format_municipality(
                    self._repository.get_municipality(address_code.lg_code), selected_format
                )
            case AddressLevel.TOWN:
                if address_code.machiaza_id is None:
                    raise RuntimeError("A town-level code must have a machiaza_id.")
                town = self._repository.get_town(address_code.lg_code, address_code.machiaza_id)
                if not town.is_registered and address_code.lot.numbers:
                    raise ValueError(
                        f"{address_code} has lot numbers, but {town.oaza_name} takes lot "
                        + "numbers only under a chome."
                    )
                return self._formatter.format_town(town, address_code.lot, selected_format)
