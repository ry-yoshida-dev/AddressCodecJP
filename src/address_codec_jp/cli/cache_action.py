from enum import Enum


class CacheAction(Enum):
    """
    Action of the ``cache`` command on the default database.

    Attributes
    ----------
    INFO
        Show the path, build time, size, and the municipalities added on demand.
    CLEAR
        Delete the database and obsolete files.
    REFRESH
        Download again everything the database holds.
    PREPARE
        Download the data of whole prefectures or municipalities ahead of use.
    """

    INFO = "info"
    CLEAR = "clear"
    REFRESH = "refresh"
    PREPARE = "prepare"
