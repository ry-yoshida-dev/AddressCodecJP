import argparse
import sqlite3
import sys
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import assert_never

from address_codec_jp.address_codec import AddressCodec
from address_codec_jp.database.cache import DatabaseCache
from address_codec_jp.frontends.cli.command import Command
from address_codec_jp.frontends.cli.command_arguments import CommandArguments
from address_codec_jp.frontends.cli.database_maintainer import DatabaseMaintainer
from address_codec_jp.frontends.cli.parser_factory import ParserFactory
from address_codec_jp.frontends.cli.query_answerer import QueryAnswerer
from address_codec_jp.frontends.cli.record_writer import RecordWriter


class CommandLineInterface:
    """
    Command line front end of ``AddressCodec`` and ``RegistryImporter``.

    Query commands read their inputs from the arguments, or from standard input, one
    per line, when no argument is given. Standard input is processed line by line, and
    blank lines are reported as errors so that JSON Lines output stays aligned with the
    input lines.
    """

    def __init__(self) -> None:
        self._parser: argparse.ArgumentParser = ParserFactory().build()
        self._maintainer: DatabaseMaintainer = DatabaseMaintainer()

    def run(self, arguments: Sequence[str] | None = None) -> int:
        """
        Execute a command.

        Parameters
        ----------
        arguments : Sequence[str] | None
            Command line arguments. ``sys.argv`` is used when omitted.

        Returns
        -------
        int
            Process exit status.
        """
        namespace = self._parser.parse_args(arguments, namespace=CommandArguments())
        command = Command(namespace.command)
        try:
            return self._execute(command, namespace)
        except (LookupError, ValueError, OSError, RuntimeError, sqlite3.Error) as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 1

    def _execute(self, command: Command, namespace: CommandArguments) -> int:
        if command is Command.CACHE:
            if namespace.database is not None:
                raise ValueError("cache manages the default database; omit --database.")
            self._maintainer.manage_cache(DatabaseCache.default(), namespace)
            return 0
        database_path = self._resolve_database(namespace)
        match command:
            case Command.IMPORT:
                self._maintainer.import_registry_files(
                    database_path, [Path(source) for source in namespace.sources]
                )
                return 0
            case Command.IMPORT_AREA:
                self._maintainer.import_areas(
                    database_path, [Path(source) for source in namespace.sources], namespace.lg_code
                )
                return 0
            case Command.DOWNLOAD:
                self._maintainer.download(namespace, database_path)
                return 0
            case Command.INFO:
                self._maintainer.print_imports(database_path)
                return 0
            case (
                Command.ENCODE
                | Command.DECODE
                | Command.LOCATE
                | Command.NEAREST
                | Command.POSTAL
                | Command.CHILDREN
                | Command.NAME
                | Command.AREA
                | Command.AREA_AT
            ):
                writer = RecordWriter(namespace.output)
                with AddressCodec.open(database_path) as codec:
                    return self._query(command, QueryAnswerer(codec), namespace, writer)
            case _:
                assert_never(command)

    def _resolve_database(self, namespace: CommandArguments) -> Path:
        if namespace.database is not None:
            return Path(namespace.database)
        cache = DatabaseCache.default()
        if not cache.is_built:
            print(
                f"Building the address database in {cache.path}; this runs only once.",
                file=sys.stderr,
            )
        return cache.ensure()

    def _query(
        self,
        command: Command,
        answerer: QueryAnswerer,
        namespace: CommandArguments,
        writer: RecordWriter,
    ) -> int:
        exit_status = 0
        for input_text in self._read_inputs(namespace.inputs):
            try:
                answerer.answer(command, namespace, writer, input_text)
            except (LookupError, ValueError) as error:
                writer.write_error(input_text, error)
                exit_status = 1
        return exit_status

    def _read_inputs(self, arguments: list[str]) -> Iterator[str]:
        if arguments:
            yield from arguments
            return
        for line in sys.stdin:
            yield line.strip()
