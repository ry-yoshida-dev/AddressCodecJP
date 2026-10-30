import json
from typing import ClassVar

from address_codec_jp.frontends.cli.output_format import OutputFormat
from address_codec_jp.frontends.serialization import ErrorSerializer, JsonValue


class RecordWriter:
    """
    Writer of one result or error per input of a query command, on standard output.

    Tab-separated lines start with the input, so that results that span several lines,
    empty results, and failures can all be matched to their input.

    Parameters
    ----------
    output_format : OutputFormat
        Tab-separated text or JSON Lines.
    """

    ERROR_MARKER: ClassVar[str] = "ERROR"

    _SEPARATOR_TRANSLATION: ClassVar[dict[int, str]] = str.maketrans(
        {"\t": " ", "\n": " ", "\r": " "}
    )

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
            Lines of values written as tab-separated text after the input, usually one;
            none writes the input alone.
        fields : dict[str, JsonValue]
            Values written as one JSON object after ``input``.
        """
        match self._output_format:
            case OutputFormat.TSV:
                for row in rows or [[]]:
                    self._print_row([input_text, *row])
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
            Raised error. Tab-separated text writes the input, ``ERROR``, the type name,
            and the message; JSON Lines also lists the candidate codes of an
            ``AmbiguousAddressError``.
        """
        fields: dict[str, JsonValue] = self._error_serializer.serialize(error)
        match self._output_format:
            case OutputFormat.TSV:
                self._print_row(
                    [input_text, self.ERROR_MARKER, str(fields["error_type"]), str(fields["error"])]
                )
            case OutputFormat.JSONL:
                print(json.dumps({"input": input_text, **fields}, ensure_ascii=False))

    def _print_row(self, values: list[str]) -> None:
        print("\t".join(value.translate(self._SEPARATOR_TRANSLATION) for value in values))
