from address_codec_jp.frontends.cli.cache_action import CacheAction
from address_codec_jp.frontends.cli.command import Command
from address_codec_jp.frontends.cli.command_arguments import CommandArguments
from address_codec_jp.frontends.cli.command_line_interface import CommandLineInterface
from address_codec_jp.frontends.cli.database_maintainer import DatabaseMaintainer
from address_codec_jp.frontends.cli.enum_argument import EnumArgument
from address_codec_jp.frontends.cli.exit_status import ExitStatus
from address_codec_jp.frontends.cli.output_format import OutputFormat
from address_codec_jp.frontends.cli.parser_factory import ParserFactory
from address_codec_jp.frontends.cli.query_answerer import QueryAnswerer
from address_codec_jp.frontends.cli.record_writer import RecordWriter


def main() -> None:
    """Entry point of the ``address-codec-jp`` command."""
    raise SystemExit(CommandLineInterface().run())


__all__ = [
    "CacheAction",
    "Command",
    "CommandArguments",
    "CommandLineInterface",
    "DatabaseMaintainer",
    "EnumArgument",
    "ExitStatus",
    "OutputFormat",
    "ParserFactory",
    "QueryAnswerer",
    "RecordWriter",
    "main",
]
