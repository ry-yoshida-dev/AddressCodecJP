from enum import Enum


class Command(Enum):
    """
    Sub-commands of the command line interface.

    The query commands bear the names of the batch operations of the web API.
    """

    IMPORT = "import"
    IMPORT_AREA = "import-area"
    DOWNLOAD = "download"
    INFO = "info"
    CACHE = "cache"
    ENCODE = "encode"
    DECODE = "decode"
    LOCATE = "locate"
    LOCATE_CODE = "locate-code"
    NEAREST = "nearest"
    POSTAL = "postal"
    CHILDREN = "children"
    NAME = "name"
    AREA = "area"
    AREA_CODE = "area-code"
    AREAS_AT = "areas-at"
