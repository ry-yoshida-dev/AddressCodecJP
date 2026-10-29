import argparse

from geo_coordinate import GeodeticCrs

from address_codec_jp.cli.cache_action import CacheAction
from address_codec_jp.cli.output_format import OutputFormat
from address_codec_jp.formatting.digit_width import DigitWidth
from address_codec_jp.formatting.lot_style import LotStyle
from address_codec_jp.formatting.numeral_style import NumeralStyle


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
        self.command: str = ""
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
        self.crs: GeodeticCrs = GeodeticCrs.JGD2011
        self.max_distance: float = 0.0
        self.directory: str = ""
        self.prefectures: list[str] = []
        self.municipalities: list[str] = []
        self.is_imported: bool = False
        self.is_existing_kept: bool = False
        self.is_area_excluded: bool = False
        self.base_url: str = ""
