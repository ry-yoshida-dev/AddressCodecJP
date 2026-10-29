from address_codec_jp.cli.command import Command
from address_codec_jp.cli.command_arguments import CommandArguments
from address_codec_jp.cli.command_line_interface import CommandLineInterface
from address_codec_jp.cli.coordinate_text import CoordinateText
from address_codec_jp.cli.output_format import OutputFormat
from address_codec_jp.cli.output_value import OutputValue
from address_codec_jp.cli.record_writer import RecordWriter


def main() -> None:
    """Entry point of the ``address-codec-jp`` command."""
    raise SystemExit(CommandLineInterface().run())


__all__ = [
    "Command",
    "CommandArguments",
    "CommandLineInterface",
    "CoordinateText",
    "OutputFormat",
    "OutputValue",
    "RecordWriter",
    "main",
]
