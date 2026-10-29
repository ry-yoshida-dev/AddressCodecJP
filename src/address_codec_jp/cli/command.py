from enum import Enum


class Command(Enum):
    """Sub-commands of the command line interface."""

    IMPORT = "import"
    ENCODE = "encode"
    DECODE = "decode"
    IMPORT_POSITIONS = "import-positions"
    LOCATE = "locate"
    NEAREST = "nearest"
    INFO = "info"
