from enum import Enum


class MaintenanceCommand(Enum):
    """
    Sub-commands that prepare or inspect the database.

    The query sub-commands are the ``QueryOperation`` values, named like the batch
    operations of the web API.
    """

    IMPORT = "import"
    IMPORT_AREA = "import-area"
    DOWNLOAD = "download"
    INFO = "info"
    CACHE = "cache"
