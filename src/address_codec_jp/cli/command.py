from enum import Enum


class Command(Enum):
    """Sub-commands of the command line interface."""

    IMPORT = "import"
    DOWNLOAD = "download"
    INFO = "info"
    ENCODE = "encode"
    DECODE = "decode"
    LOCATE = "locate"
    NEAREST = "nearest"
    POSTAL = "postal"
