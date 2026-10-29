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
from address_codec_jp.cli.output_format import OutputFormat
from address_codec_jp.cli.record_writer import RecordWriter
from address_codec_jp.formatting.address_format import AddressFormat
from address_codec_jp.formatting.digit_width import DigitWidth
from address_codec_jp.formatting.lot_style import LotStyle
from address_codec_jp.formatting.name_script import NameScript
from address_codec_jp.formatting.numeral_style import NumeralStyle
from address_codec_jp.registry_importer import RegistryImporter


class CommandLineInterface:
    """
    Command line front end of ``AddressCodec``.

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
        database_path = Path(namespace.database)
        match command:
            case Command.IMPORT:
                with RegistryImporter.open(database_path) as importer:
                    summary = importer.import_town_master(Path(namespace.source))
                print(
                    f"Imported {summary.registered_count} towns and added "
                    + f"{summary.complemented_count} oaza-level towns into {database_path}; "
                    + f"removed {summary.removed_position_count} position rows of other towns."
                )
                return 0
            case Command.IMPORT_POSITIONS:
                with RegistryImporter.open(database_path) as importer:
                    for source in namespace.sources:
                        position_summary = importer.import_positions(Path(source))
                        print(
                            f"Imported {position_summary.stored_count} rows of "
                            + f"{position_summary.dataset.value} from {source}; removed "
                            + f"{position_summary.removed_count} abolished lots."
                        )
                return 0
            case Command.ENCODE | Command.DECODE | Command.LOCATE | Command.NEAREST:
                writer = RecordWriter(OutputFormat(namespace.output))
                with AddressCodec.open(database_path) as codec:
                    return self._query(command, codec, namespace, writer)
            case _:
                assert_never(command)

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
                    [str(address_match.code), address_match.remainder]
                    if address_match.remainder
                    else [str(address_match.code)],
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
                writer.write(input_text, [address], {"address": address})
            case Command.LOCATE:
                location = codec.locate(input_text, GeodeticCrs[namespace.crs.upper()])
                writer.write(
                    input_text,
                    [
                        str(location.code),
                        str(location.located_code),
                        location.level.name,
                        f"{location.latitude_degrees:.9f}",
                        f"{location.longitude_degrees:.9f}",
                        str(location.crs),
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
                    self._coordinate_text.parse(input_text),
                    GeodeticCrs[namespace.crs.upper()],
                    namespace.max_distance,
                )
                location = nearest.location
                address = codec.decode(nearest.code)
                writer.write(
                    input_text,
                    [
                        str(nearest.code),
                        address,
                        location.level.name,
                        f"{location.latitude_degrees:.9f}",
                        f"{location.longitude_degrees:.9f}",
                        f"{nearest.distance_meters:.1f}",
                        str(location.crs),
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
            case Command.IMPORT | Command.IMPORT_POSITIONS:
                raise RuntimeError(f"{command.value} is not a query command.")
            case _:
                assert_never(command)

    def _address_format(self, namespace: CommandArguments) -> AddressFormat:
        return AddressFormat(
            numeral_style=NumeralStyle[namespace.numeral.upper()],
            lot_style=LotStyle[namespace.lot.upper()],
            digit_width=DigitWidth[namespace.width.upper()],
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
            "--database", default="towns.sqlite3", help="SQLite town database path."
        )
        subparsers = parser.add_subparsers(dest="command", required=True)

        query_parser = argparse.ArgumentParser(add_help=False)
        _ = query_parser.add_argument(
            "--output",
            choices=[output_format.value for output_format in OutputFormat],
            default=OutputFormat.TSV.value,
            help="tsv, or jsonl with one object per input including errors.",
        )
        crs_parser = argparse.ArgumentParser(add_help=False)
        _ = crs_parser.add_argument(
            "--crs",
            choices=[crs.name.lower() for crs in GeodeticCrs],
            default=GeodeticCrs.JGD2011.name.lower(),
        )

        import_parser = subparsers.add_parser(
            Command.IMPORT.value, help="Import the Address Base Registry town master."
        )
        _ = import_parser.add_argument("source", help="mt_town_all.csv or its ZIP archive.")

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
            Command.DECODE.value, parents=[query_parser], help="Code to address."
        )
        _ = decode_parser.add_argument(
            "inputs", nargs="*", metavar="code", help="Address codes; standard input if none."
        )
        _ = decode_parser.add_argument(
            "--numeral",
            choices=[style.name.lower() for style in NumeralStyle],
            default=NumeralStyle.ARABIC.name.lower(),
        )
        _ = decode_parser.add_argument(
            "--lot",
            choices=[style.name.lower() for style in LotStyle],
            default=LotStyle.RESIDENCE_INDICATION.name.lower(),
        )
        _ = decode_parser.add_argument(
            "--width",
            choices=[width.name.lower() for width in DigitWidth],
            default=DigitWidth.HALF.name.lower(),
        )
        _ = decode_parser.add_argument(
            "--no-prefecture", dest="is_prefecture_excluded", action="store_true"
        )
        _ = decode_parser.add_argument(
            "--no-county", dest="is_county_excluded", action="store_true"
        )
        _ = decode_parser.add_argument(
            "--kana", dest="is_kana", action="store_true", help="Write katakana readings."
        )
        _ = decode_parser.add_argument(
            "--postal-code",
            dest="is_postal_code_included",
            action="store_true",
            help="Prefix the registered postal code of the town.",
        )

        positions_parser = subparsers.add_parser(
            Command.IMPORT_POSITIONS.value,
            help="Import position datasets and block, residence, or parcel masters.",
        )
        _ = positions_parser.add_argument(
            "sources", nargs="+", help="Registry CSV files or their ZIP archives."
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
        return parser
