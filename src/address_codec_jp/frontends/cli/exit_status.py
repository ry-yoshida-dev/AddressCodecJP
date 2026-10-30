from enum import IntEnum


class ExitStatus(IntEnum):
    """
    Exit status of the ``address-codec-jp`` command.

    Attributes
    ----------
    SUCCESS
        The command completed and every input was answered.
    INPUT_FAILURE
        The command completed, but at least one input failed; each failure is written
        in place of its result.
    USAGE_ERROR
        The arguments are invalid; set by the argument parser.
    FATAL_ERROR
        The command could not run or stopped, such as when the database cannot be
        opened or a file cannot be imported.
    """

    SUCCESS = 0
    INPUT_FAILURE = 1
    USAGE_ERROR = 2
    FATAL_ERROR = 3
