import argparse

from geo_coordinate import GeodeticCrs

from address_codec_jp.address_codec import AddressCodec
from address_codec_jp.frontends.cli.cache_action import CacheAction
from address_codec_jp.frontends.cli.maintenance_command import MaintenanceCommand
from address_codec_jp.frontends.cli.output_format import OutputFormat
from address_codec_jp.frontends.query import QueryOperation, QueryOptions
from address_codec_jp.text.formatting import (
    AddressFormat,
    DigitWidth,
    LotStyle,
    NameScript,
    NumeralStyle,
)


class CommandArguments(argparse.Namespace):
    """
    Typed namespace populated by the command line parser.

    The parser does not apply the default of a top-level option to an attribute that
    the namespace already has, so top-level attributes start from their real defaults.
    Sub-command attributes are parsed into a fresh namespace and copied over, so their
    initial values here are only placeholders.
    """

    def __init__(self) -> None:
        super().__init__()
        self.database: str | None = None
        self.command: MaintenanceCommand | QueryOperation = MaintenanceCommand.INFO
        self.cache_action: CacheAction = CacheAction.INFO
        self.sources: list[str] = []
        self.lg_code: str = ""
        self.inputs: list[str] = []
        self.output: OutputFormat = OutputFormat.TSV
        self.numeral: NumeralStyle = NumeralStyle.ARABIC
        self.lot: LotStyle = LotStyle.AUTOMATIC
        self.width: DigitWidth = DigitWidth.HALF
        self.is_prefecture_excluded: bool = False
        self.is_county_excluded: bool = False
        self.is_kana: bool = False
        self.is_postal_code_included: bool = False
        self.is_lot_verified: bool = False
        self.is_parcel_included: bool = False
        self.is_geometry_included: bool = True
        self.crs: GeodeticCrs = GeodeticCrs.JGD2011
        self.max_distance: float = AddressCodec.DEFAULT_MAX_DISTANCE_METERS
        self.directory: str = ""
        self.prefectures: list[str] = []
        self.municipalities: list[str] = []
        self.is_imported: bool = False
        self.is_existing_kept: bool = False
        self.is_area_excluded: bool = False
        self.base_url: str = ""

    def to_query_options(self) -> QueryOptions:
        """
        Build the options of a query command.

        Returns
        -------
        QueryOptions
            Format, datum, distance, parcel, and geometry options parsed for the command.
        """
        return QueryOptions(
            address_format=AddressFormat(
                numeral_style=self.numeral,
                lot_style=self.lot,
                digit_width=self.width,
                is_prefecture_included=not self.is_prefecture_excluded,
                is_county_included=not self.is_county_excluded,
                name_script=NameScript.KATAKANA if self.is_kana else NameScript.KANJI,
                is_postal_code_included=self.is_postal_code_included,
            ),
            is_lot_verified=self.is_lot_verified,
            crs=self.crs,
            max_distance_meters=self.max_distance,
            is_parcel_included=self.is_parcel_included,
            is_geometry_included=self.is_geometry_included,
        )
