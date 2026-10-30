from enum import Enum


class OutputFormat(Enum):
    """
    Output format of query commands.

    Attributes
    ----------
    TSV
        Tab-separated lines that start with the input: one per result row, the input
        alone for an empty result, and ``ERROR``, the error type, and the message for a
        failure, so that every input is represented.
    JSONL
        One JSON object per input, including errors, so that lines align with inputs.
    """

    TSV = "tsv"
    JSONL = "jsonl"
