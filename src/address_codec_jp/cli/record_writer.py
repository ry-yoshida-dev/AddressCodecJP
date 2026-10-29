import json
import sys

from address_codec_jp.cli.output_format import OutputFormat
from address_codec_jp.cli.output_value import OutputValue


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

    def write(self, input_text: str, columns: list[str], fields: dict[str, OutputValue]) -> None:
        """
        Write the result of one input.

        Parameters
        ----------
        input_text : str
            Input the result belongs to.
        columns : list[str]
            Values written as tab-separated text.
        fields : dict[str, OutputValue]
            Values written as a JSON object after ``input``.
        """
        match self._output_format:
            case OutputFormat.TSV:
                print("\t".join(columns))
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
            Raised error.
        """
        match self._output_format:
            case OutputFormat.TSV:
                print(f"{input_text}\tERROR: {error}", file=sys.stderr)
            case OutputFormat.JSONL:
                print(json.dumps({"input": input_text, "error": str(error)}, ensure_ascii=False))
