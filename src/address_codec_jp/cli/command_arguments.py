import argparse


class CommandArguments(argparse.Namespace):
    """Typed namespace populated by the command line parser."""

    def __init__(self) -> None:
        super().__init__()
        self.command: str = ""
        self.database: str = ""
        self.source: str = ""
        self.sources: list[str] = []
        self.inputs: list[str] = []
        self.output: str = ""
        self.numeral: str = ""
        self.lot: str = ""
        self.width: str = ""
        self.is_prefecture_excluded: bool = False
        self.is_county_excluded: bool = False
        self.is_kana: bool = False
        self.is_postal_code_included: bool = False
        self.is_lot_verified: bool = False
        self.crs: str = ""
        self.max_distance: float = 0.0
        self.directory: str = ""
        self.prefectures: list[str] = []
        self.municipalities: list[str] = []
        self.is_imported: bool = False
        self.is_existing_kept: bool = False
        self.base_url: str = ""
