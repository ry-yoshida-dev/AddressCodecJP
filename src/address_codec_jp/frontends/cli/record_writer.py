import json
import sys

from address_codec_jp.frontends.cli.output_format import OutputFormat
from address_codec_jp.frontends.serialization import ErrorSerializer, JsonValue


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
        self._error_serializer: ErrorSerializer = ErrorSerializer()

    def write(self, input_text: str, rows: list[list[str]], fields: dict[str, JsonValue]) -> None:
        """
        Write the result of one input.

        Parameters
        ----------
        input_text : str
            Input the result belongs to.
        rows : list[list[str]]
            Lines of values written as tab-separated text, usually one.
        fields : dict[str, JsonValue]
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
                fields: dict[str, JsonValue] = {
                    "input": input_text,
                    **self._error_serializer.serialize(error),
                }
                print(json.dumps(fields, ensure_ascii=False))
