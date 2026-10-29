from address_codec_jp.frontends.cli.cache_action import CacheAction
from address_codec_jp.frontends.cli.command import Command
from address_codec_jp.frontends.cli.command_arguments import CommandArguments
from address_codec_jp.frontends.cli.command_line_interface import CommandLineInterface
from address_codec_jp.frontends.cli.enum_argument import EnumArgument
from address_codec_jp.frontends.cli.output_format import OutputFormat
from address_codec_jp.frontends.cli.record_writer import RecordWriter


def main() -> None:
    """Entry point of the ``address-codec-jp`` command."""
    raise SystemExit(CommandLineInterface().run())


__all__ = [
    "CacheAction",
    "Command",
    "CommandArguments",
    "CommandLineInterface",
    "EnumArgument",
    "OutputFormat",
    "RecordWriter",
    "main",
]
