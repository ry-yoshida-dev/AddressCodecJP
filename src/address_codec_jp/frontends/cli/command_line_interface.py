import argparse
import sqlite3
import sys
from collections.abc import Generator, Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import ClassVar, assert_never

from progress_bar import ProgressBarGroup

from address_codec_jp.address_codec import AddressCodec
from address_codec_jp.database.cache import DatabaseCache
from address_codec_jp.errors import AddressCodecError
from address_codec_jp.frontends.cli.command_arguments import CommandArguments
from address_codec_jp.frontends.cli.database_maintainer import DatabaseMaintainer
from address_codec_jp.frontends.cli.exit_status import ExitStatus
from address_codec_jp.frontends.cli.maintenance_command import MaintenanceCommand
from address_codec_jp.frontends.cli.parser_factory import ParserFactory
from address_codec_jp.frontends.cli.record_writer import RecordWriter
from address_codec_jp.frontends.query import (
    DirectInterpreter,
    PassThroughGuard,
    QueryOperation,
    QueryRunner,
)


class CommandLineInterface:
    """
    Command line front end of ``AddressCodec`` and ``RegistryImporter``.

    Query commands read their inputs from the arguments, or from standard input, one
    per line, when no argument is given. Standard input is processed line by line. An
    input that fails, including a blank line, a malformed or unregistered input, data
    not imported, or a database error, is written as an error record in place of its
    result and the next input is processed, so that the output stays aligned with the
    inputs. See ``ExitStatus`` for the exit statuses.
    """

    _INPUT_ERRORS: ClassVar[tuple[type[Exception], ...]] = (
        AddressCodecError,
        LookupError,
        ValueError,
        OverflowError,
        sqlite3.Error,
    )

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
            ``ExitStatus`` of the process.
        """
        namespace = self._parser.parse_args(arguments, namespace=CommandArguments())
        try:
            with ProgressBarGroup() as progress:
                return int(self._execute(namespace, progress))
        except (
            AddressCodecError,
            LookupError,
            ValueError,
            OSError,
            RuntimeError,
            sqlite3.Error,
        ) as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return int(ExitStatus.FATAL_ERROR)

    def _execute(self, namespace: CommandArguments, progress: ProgressBarGroup) -> ExitStatus:
        command = namespace.command
        match command:
            case MaintenanceCommand.CACHE:
                if namespace.database is not None:
                    raise ValueError("cache manages the default database; omit --database.")
                self._maintainer.manage_cache(DatabaseCache.default(progress=progress), namespace)
            case MaintenanceCommand.IMPORT:
                with self._open_for_import(namespace, progress) as database_path:
                    self._maintainer.import_registry_files(
                        database_path, [Path(source) for source in namespace.sources]
                    )
            case MaintenanceCommand.IMPORT_AREA:
                with self._open_for_import(namespace, progress) as database_path:
                    self._maintainer.import_areas(
                        database_path,
                        [Path(source) for source in namespace.sources],
                        namespace.lg_code,
                    )
            case MaintenanceCommand.DOWNLOAD:
                paths = self._maintainer.download(namespace)
                if namespace.is_imported:
                    with self._open_for_import(namespace, progress) as database_path:
                        self._maintainer.import_registry_files(database_path, paths)
            case MaintenanceCommand.INFO:
                database_path = (
                    Path(namespace.database)
                    if namespace.database is not None
                    else self._default_cache(progress).ensure()
                )
                self._maintainer.print_imports(database_path)
            case QueryOperation() as operation:
                with self._open_codec(namespace, progress) as codec:
                    runner = QueryRunner(codec, DirectInterpreter(), PassThroughGuard())
                    return self._query(operation, runner, namespace)
            case _:
                assert_never(command)
        return ExitStatus.SUCCESS

    def _open_codec(self, namespace: CommandArguments, progress: ProgressBarGroup) -> AddressCodec:
        if namespace.database is not None:
            return AddressCodec.open(namespace.database)
        return AddressCodec.open(cache=self._default_cache(progress))

    @contextmanager
    def _open_for_import(
        self, namespace: CommandArguments, progress: ProgressBarGroup
    ) -> Generator[Path]:
        if namespace.database is not None:
            yield Path(namespace.database)
            return
        with self._default_cache(progress).locked_for_import() as database_path:
            yield database_path

    def _default_cache(self, progress: ProgressBarGroup) -> DatabaseCache:
        cache = DatabaseCache.default(progress=progress)
        if not cache.is_built:
            print(
                f"Building the address database in {cache.path}; this runs only once.",
                file=sys.stderr,
            )
        return cache

    def _query(
        self,
        operation: QueryOperation,
        runner: QueryRunner,
        namespace: CommandArguments,
    ) -> ExitStatus:
        options = namespace.to_query_options()
        writer = RecordWriter(namespace.output)
        exit_status = ExitStatus.SUCCESS
        for input_text in self._read_inputs(namespace.inputs):
            try:
                writer.write(input_text, runner.run(operation, input_text, options))
            except self._INPUT_ERRORS as error:
                writer.write_error(input_text, error)
                exit_status = ExitStatus.INPUT_FAILURE
        return exit_status

    def _read_inputs(self, arguments: list[str]) -> Iterator[str]:
        if arguments:
            yield from arguments
            return
        for line in sys.stdin:
            yield line.strip()
