from address_codec_jp.cli.command import Command
from address_codec_jp.cli.command_arguments import CommandArguments
from address_codec_jp.cli.command_line_interface import CommandLineInterface


def main() -> None:
    """Entry point of the ``address-codec-jp`` command."""
    raise SystemExit(CommandLineInterface().run())


__all__ = ["Command", "CommandArguments", "CommandLineInterface", "main"]
