from enum import Enum


class Command(Enum):
    """Sub-commands of the command line interface."""

    IMPORT = "import"
    IMPORT_AREA = "import-area"
    DOWNLOAD = "download"
    INFO = "info"
    CACHE = "cache"
    ENCODE = "encode"
    DECODE = "decode"
    LOCATE = "locate"
    NEAREST = "nearest"
    POSTAL = "postal"
    AREA = "area"
    AREA_AT = "area-at"
