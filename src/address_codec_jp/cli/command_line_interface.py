import argparse
import sqlite3
import sys
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import assert_never

from geo_coordinate import GeodeticCrs

from address_codec_jp.address_codec import AddressCodec
from address_codec_jp.cli.command import Command
from address_codec_jp.cli.command_arguments import CommandArguments
from address_codec_jp.cli.coordinate_text import CoordinateText
from address_codec_jp.cli.enum_argument import EnumArgument
from address_codec_jp.cli.output_format import OutputFormat
from address_codec_jp.cli.output_value import OutputValue
from address_codec_jp.cli.record_writer import RecordWriter
from address_codec_jp.database_cache import DatabaseCache
from address_codec_jp.download.registry_downloader import RegistryDownloader
from address_codec_jp.errors.address_not_found_error import AddressNotFoundError
from address_codec_jp.formatting.address_format import AddressFormat
from address_codec_jp.formatting.digit_width import DigitWidth
from address_codec_jp.formatting.lot_style import LotStyle
from address_codec_jp.formatting.name_script import NameScript
from address_codec_jp.formatting.numeral_style import NumeralStyle
from address_codec_jp.registry.import_summary import ImportSummary
from address_codec_jp.registry_importer import RegistryImporter


class CommandLineInterface:
    """
    Command line front end of ``AddressCodec`` and ``RegistryImporter``.

    Query commands read their inputs from the arguments, or from standard input, one
    per line, when no argument is given. Standard input is processed line by line, and
    blank lines are reported as errors so that JSON Lines output stays aligned with the
    input lines.
    """

    def __init__(self) -> None:
        self._parser: argparse.ArgumentParser = self._build_parser()
        self._coordinate_text: CoordinateText = CoordinateText()

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
        database_path = self._resolve_database(namespace)
        match command:
            case Command.IMPORT:
                self._import(database_path, [Path(source) for source in namespace.sources])
                return 0
            case Command.DOWNLOAD:
                self._download(namespace, database_path)
                return 0
            case Command.INFO:
                with AddressCodec.open(database_path) as codec:
                    for dataset_import in codec.list_imports():
                        print(
                            "\t".join(
                                [
                                    dataset_import.imported_at.isoformat(timespec="seconds"),
                                    dataset_import.dataset.value,
                                    str(dataset_import.row_count),
                                    dataset_import.source_name,
                                    dataset_import.source_sha256,
                                ]
                            )
                        )
                return 0
            case (
                Command.ENCODE | Command.DECODE | Command.LOCATE | Command.NEAREST | Command.POSTAL
            ):
                writer = RecordWriter(namespace.output)
                with AddressCodec.open(database_path) as codec:
                    return self._query(command, codec, namespace, writer)
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

    def _import(self, database_path: Path, sources: list[Path]) -> None:
        with RegistryImporter.open(database_path) as importer:
            for summary in importer.import_files(sources):
                self._report(summary)

    def _report(self, summary: ImportSummary) -> None:
        complemented = (
            f", added {summary.complemented_count} oaza-level towns"
            if summary.complemented_count
            else ""
        )
        print(
            f"Imported {summary.stored_count} rows of {summary.dataset.value} from "
            + f"{summary.source}{complemented}; removed {summary.removed_count} rows."
        )

    def _download(self, namespace: CommandArguments, database_path: Path) -> None:
        downloader = RegistryDownloader(namespace.base_url)
        directory = Path(namespace.directory)
        paths: list[Path] = []
        for target in downloader.plan(namespace.prefectures, namespace.municipalities):
            path = downloader.download(
                target, directory, is_existing_kept=namespace.is_existing_kept
            )
            print(f"Downloaded {downloader.url_of(target)} to {path}")
            paths.append(path)
        if namespace.is_imported:
            self._import(database_path, paths)

    def _query(
        self,
        command: Command,
        codec: AddressCodec,
        namespace: CommandArguments,
        writer: RecordWriter,
    ) -> int:
        exit_status = 0
        for input_text in self._read_inputs(namespace.inputs):
            try:
                self._answer(command, codec, namespace, writer, input_text)
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

    def _answer(
        self,
        command: Command,
        codec: AddressCodec,
        namespace: CommandArguments,
        writer: RecordWriter,
        input_text: str,
    ) -> None:
        match command:
            case Command.ENCODE:
                address_match = codec.match(input_text, is_lot_verified=namespace.is_lot_verified)
                writer.write(
                    input_text,
                    [
                        [str(address_match.code), address_match.remainder]
                        if address_match.remainder
                        else [str(address_match.code)]
                    ],
                    {
                        "code": str(address_match.code),
                        "level": address_match.code.level.name,
                        "remainder": address_match.remainder,
                        "town_name_tier": None
                        if address_match.town_name_tier is None
                        else address_match.town_name_tier.name,
                    },
                )
            case Command.DECODE:
                address = codec.decode(input_text, self._address_format(namespace))
                writer.write(input_text, [[address]], {"address": address})
            case Command.LOCATE:
                location = codec.locate(input_text, namespace.crs)
                writer.write(
                    input_text,
                    [
                        [
                            str(location.code),
                            str(location.located_code),
                            location.level.name,
                            f"{location.latitude_degrees:.9f}",
                            f"{location.longitude_degrees:.9f}",
                            str(location.crs),
                        ]
                    ],
                    {
                        "code": str(location.code),
                        "located_code": str(location.located_code),
                        "level": location.level.name,
                        "latitude": location.latitude_degrees,
                        "longitude": location.longitude_degrees,
                        "crs": str(location.crs),
                    },
                )
            case Command.NEAREST:
                nearest = codec.find_nearest(
                    self._coordinate_text.parse(input_text), namespace.crs, namespace.max_distance
                )
                location = nearest.location
                address = codec.decode(nearest.code)
                writer.write(
                    input_text,
                    [
                        [
                            str(nearest.code),
                            address,
                            location.level.name,
                            f"{location.latitude_degrees:.9f}",
                            f"{location.longitude_degrees:.9f}",
                            f"{nearest.distance_meters:.1f}",
                            str(location.crs),
                        ]
                    ],
                    {
                        "code": str(nearest.code),
                        "address": address,
                        "level": location.level.name,
                        "latitude": location.latitude_degrees,
                        "longitude": location.longitude_degrees,
                        "distance_meters": nearest.distance_meters,
                        "crs": str(location.crs),
                    },
                )
            case Command.POSTAL:
                address_format = self._address_format(namespace)
                towns = [
                    (str(address.code), codec.decode(address.code, address_format))
                    for address in codec.list_by_postal_code(input_text)
                ]
                if not towns:
                    raise AddressNotFoundError(f"No town is registered with {input_text!r}.")
                town_values: list[OutputValue] = [
                    {"code": code, "address": address} for code, address in towns
                ]
                writer.write(
                    input_text,
                    [[code, address] for code, address in towns],
                    {"towns": town_values},
                )
            case Command.IMPORT | Command.DOWNLOAD | Command.INFO:
                raise RuntimeError(f"{command.value} is not a query command.")
            case _:
                assert_never(command)

    def _address_format(self, namespace: CommandArguments) -> AddressFormat:
        return AddressFormat(
            numeral_style=namespace.numeral,
            lot_style=namespace.lot,
            digit_width=namespace.width,
            is_prefecture_included=not namespace.is_prefecture_excluded,
            is_county_included=not namespace.is_county_excluded,
            name_script=NameScript.KATAKANA if namespace.is_kana else NameScript.KANJI,
            is_postal_code_included=namespace.is_postal_code_included,
        )

    def _build_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            prog="address-codec-jp",
            description="Convert Japanese addresses to and from address codes.",
        )
        _ = parser.add_argument(
            "--database",
            help="SQLite address database path. By default, a database of all towns is "
            + "downloaded and built once in the user cache directory.",
        )
        subparsers = parser.add_subparsers(dest="command", required=True)

        query_parser = argparse.ArgumentParser(add_help=False)
        output_argument = EnumArgument(OutputFormat)
        _ = query_parser.add_argument(
            "--output",
            type=output_argument,
            metavar=output_argument.metavar,
            default=OutputFormat.TSV,
            help="tsv, or jsonl with one object per input including errors.",
        )
        crs_parser = argparse.ArgumentParser(add_help=False)
        crs_argument = EnumArgument(GeodeticCrs)
        _ = crs_parser.add_argument(
            "--crs",
            type=crs_argument,
            metavar=crs_argument.metavar,
            default=GeodeticCrs.JGD2011,
            help="Datum of coordinates (jgd2011 by default).",
        )
        format_parser = argparse.ArgumentParser(add_help=False)
        self._add_format_arguments(format_parser)

        import_parser = subparsers.add_parser(
            Command.IMPORT.value,
            help="Import registry files of any dataset; the town master is imported first.",
        )
        _ = import_parser.add_argument(
            "sources", nargs="+", help="Registry CSV files or their ZIP archives."
        )

        download_parser = subparsers.add_parser(
            Command.DOWNLOAD.value,
            help="Download the town master, nationwide points, and files of chosen areas.",
        )
        self._add_download_arguments(download_parser)

        _ = subparsers.add_parser(
            Command.INFO.value,
            help="List imported registry files: time, dataset, rows, file name, and SHA-256.",
        )

        encode_parser = subparsers.add_parser(
            Command.ENCODE.value, parents=[query_parser], help="Address to code."
        )
        _ = encode_parser.add_argument(
            "inputs", nargs="*", metavar="address", help="Addresses; standard input if none."
        )
        _ = encode_parser.add_argument(
            "--verify-lot",
            dest="is_lot_verified",
            action="store_true",
            help="Reject lot numbers missing from the imported block, residence, or parcel "
            + "masters.",
        )

        decode_parser = subparsers.add_parser(
            Command.DECODE.value, parents=[query_parser, format_parser], help="Code to address."
        )
        _ = decode_parser.add_argument(
            "inputs", nargs="*", metavar="code", help="Address codes; standard input if none."
        )

        locate_parser = subparsers.add_parser(
            Command.LOCATE.value,
            parents=[query_parser, crs_parser],
            help="Address to representative point.",
        )
        _ = locate_parser.add_argument(
            "inputs", nargs="*", metavar="address", help="Addresses; standard input if none."
        )

        nearest_parser = subparsers.add_parser(
            Command.NEAREST.value,
            parents=[query_parser, crs_parser],
            help="Coordinate to the address with the nearest representative point.",
        )
        _ = nearest_parser.add_argument(
            "inputs",
            nargs="*",
            metavar="latitude,longitude",
            help="Coordinates in decimal degrees; standard input if none.",
        )
        _ = nearest_parser.add_argument(
            "--max-distance",
            dest="max_distance",
            type=float,
            default=1000.0,
            help="Largest accepted distance in meters.",
        )

        postal_parser = subparsers.add_parser(
            Command.POSTAL.value,
            parents=[query_parser, format_parser],
            help="Postal code to the towns registered with it.",
        )
        _ = postal_parser.add_argument(
            "inputs",
            nargs="*",
            metavar="postal_code",
            help="Postal codes such as 100-0005; standard input if none.",
        )
        return parser

    def _add_format_arguments(self, parser: argparse.ArgumentParser) -> None:
        numeral_argument = EnumArgument(NumeralStyle)
        _ = parser.add_argument(
            "--numeral",
            type=numeral_argument,
            metavar=numeral_argument.metavar,
            default=NumeralStyle.ARABIC,
        )
        lot_argument = EnumArgument(LotStyle)
        _ = parser.add_argument(
            "--lot",
            type=lot_argument,
            metavar=lot_argument.metavar,
            default=LotStyle.AUTOMATIC,
            help="Lot notation; automatic follows the numbering system of the town.",
        )
        width_argument = EnumArgument(DigitWidth)
        _ = parser.add_argument(
            "--width",
            type=width_argument,
            metavar=width_argument.metavar,
            default=DigitWidth.HALF,
        )
        _ = parser.add_argument(
            "--no-prefecture", dest="is_prefecture_excluded", action="store_true"
        )
        _ = parser.add_argument("--no-county", dest="is_county_excluded", action="store_true")
        _ = parser.add_argument(
            "--kana", dest="is_kana", action="store_true", help="Write katakana readings."
        )
        _ = parser.add_argument(
            "--postal-code",
            dest="is_postal_code_included",
            action="store_true",
            help="Prefix the registered postal code of the town.",
        )

    def _add_download_arguments(self, parser: argparse.ArgumentParser) -> None:
        _ = parser.add_argument("directory", help="Directory for the downloaded files.")
        _ = parser.add_argument(
            "--prefecture",
            dest="prefectures",
            action="append",
            default=[],
            metavar="CODE",
            help="Two-digit prefecture code for town, block, and residence files; repeatable.",
        )
        _ = parser.add_argument(
            "--municipality",
            dest="municipalities",
            action="append",
            default=[],
            metavar="LG_CODE",
            help="Six-digit local government code for land parcel files; repeatable.",
        )
        _ = parser.add_argument(
            "--import",
            dest="is_imported",
            action="store_true",
            help="Import the downloaded files into --database.",
        )
        _ = parser.add_argument(
            "--keep-existing",
            dest="is_existing_kept",
            action="store_true",
            help="Skip files already present in the directory.",
        )
        _ = parser.add_argument(
            "--base-url",
            default=RegistryDownloader.DEFAULT_BASE_URL,
            help="Download site or a mirror, e.g. a file:// URL.",
        )
