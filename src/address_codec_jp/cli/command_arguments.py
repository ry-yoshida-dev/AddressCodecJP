import argparse


class CommandArguments(argparse.Namespace):
    """Typed namespace populated by the command line parser."""

    def __init__(self) -> None:
        super().__init__()
        self.command: str = ""
        self.database: str = ""
        self.source: str = ""
        self.sources: list[str] = []
        self.addresses: list[str] = []
        self.codes: list[str] = []
        self.numeral: str = ""
        self.lot: str = ""
        self.width: str = ""
        self.is_prefecture_excluded: bool = False
        self.is_county_excluded: bool = False
        self.crs: str = ""
