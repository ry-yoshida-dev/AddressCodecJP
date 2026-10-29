from enum import Enum


class Command(Enum):
    """Sub-commands of the command line interface."""

    IMPORT = "import"
    ENCODE = "encode"
    DECODE = "decode"
