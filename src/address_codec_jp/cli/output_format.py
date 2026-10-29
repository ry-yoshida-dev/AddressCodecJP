from enum import Enum


class OutputFormat(Enum):
    """
    Output format of query commands.

    Attributes
    ----------
    TSV
        One tab-separated line per input; errors go to standard error.
    JSONL
        One JSON object per input, including errors, so that lines align with inputs.
    """

    TSV = "tsv"
    JSONL = "jsonl"
