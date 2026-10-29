import json
import sys

from address_codec_jp.cli.output_format import OutputFormat
from address_codec_jp.cli.output_value import OutputValue
from address_codec_jp.errors.ambiguous_address_error import AmbiguousAddressError


class RecordWriter:
    """
    Writer of one result or error per input of a query command.

    Parameters
    ----------
    output_format : OutputFormat
        Tab-separated text or JSON Lines.
    """

    def __init__(self, output_format: OutputFormat) -> None:
        self._output_format: OutputFormat = output_format

    def write(self, input_text: str, rows: list[list[str]], fields: dict[str, OutputValue]) -> None:
        """
        Write the result of one input.

        Parameters
        ----------
        input_text : str
            Input the result belongs to.
        rows : list[list[str]]
            Lines of values written as tab-separated text, usually one.
        fields : dict[str, OutputValue]
            Values written as one JSON object after ``input``.
        """
        match self._output_format:
            case OutputFormat.TSV:
                for row in rows:
                    print("\t".join(row))
            case OutputFormat.JSONL:
                print(json.dumps({"input": input_text, **fields}, ensure_ascii=False))

    def write_error(self, input_text: str, error: Exception) -> None:
        """
        Write the error of one input.

        Parameters
        ----------
        input_text : str
            Input that failed.
        error : Exception
            Raised error. JSON Lines output names its type, and lists the candidate
            codes of an ``AmbiguousAddressError``.
        """
        match self._output_format:
            case OutputFormat.TSV:
                print(f"{input_text}\tERROR: {error}", file=sys.stderr)
            case OutputFormat.JSONL:
                fields: dict[str, OutputValue] = {
                    "input": input_text,
                    "error": str(error),
                    "error_type": type(error).__name__,
                }
                if isinstance(error, AmbiguousAddressError):
                    fields["candidates"] = [str(code) for code in error.candidates]
                print(json.dumps(fields, ensure_ascii=False))
