import argparse
import sqlite3
import sys
from collections.abc import Sequence
from pathlib import Path

from geo_coordinate import GeodeticCrs

from address_codec_jp.address_codec import AddressCodec
from address_codec_jp.cli.command import Command
from address_codec_jp.cli.command_arguments import CommandArguments
from address_codec_jp.formatting.address_format import AddressFormat
from address_codec_jp.formatting.digit_width import DigitWidth
from address_codec_jp.formatting.lot_style import LotStyle
from address_codec_jp.formatting.numeral_style import NumeralStyle


class CommandLineInterface:
    """Command line front end of ``AddressCodec``."""

    def __init__(self) -> None:
        self._parser: argparse.ArgumentParser = self._build_parser()

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
                with AddressCodec.create(database_path) as codec:
                    summary = codec.import_town_master(Path(namespace.source))
                print(
                    f"Imported {summary.registered_count} towns and added "
                    + f"{summary.complemented_count} oaza-level towns into {database_path}."
                )
                return 0
            case Command.ENCODE:
                with AddressCodec.open(database_path) as codec:
                    return self._encode(codec, namespace.addresses)
            case Command.DECODE:
                address_format = AddressFormat(
                    numeral_style=NumeralStyle[namespace.numeral.upper()],
                    lot_style=LotStyle[namespace.lot.upper()],
                    digit_width=DigitWidth[namespace.width.upper()],
                    is_prefecture_included=not namespace.is_prefecture_excluded,
                    is_county_included=not namespace.is_county_excluded,
                )
                with AddressCodec.open(database_path) as codec:
                    return self._decode(codec, namespace.codes, address_format)
            case Command.IMPORT_POSITIONS:
                with AddressCodec.create(database_path) as codec:
                    for source in namespace.sources:
                        position_summary = codec.import_positions(Path(source))
                        print(
                            f"Imported {position_summary.stored_count} rows of "
                            + f"{position_summary.dataset.value} from {source}."
                        )
                return 0
            case Command.LOCATE:
                with AddressCodec.open(database_path) as codec:
                    return self._locate(
                        codec, namespace.addresses, GeodeticCrs[namespace.crs.upper()]
                    )

    def _encode(self, codec: AddressCodec, addresses: list[str]) -> int:
        exit_status = 0
        for address in addresses:
            try:
                address_match = codec.match(address)
            except (LookupError, ValueError) as error:
                print(f"{address}\tERROR: {error}", file=sys.stderr)
                exit_status = 1
                continue
            print(f"{address_match.code}\t{address_match.remainder}".rstrip("\t"))
        return exit_status

    def _decode(self, codec: AddressCodec, codes: list[str], address_format: AddressFormat) -> int:
        exit_status = 0
        for code in codes:
            try:
                address = codec.decode(code, address_format)
            except (LookupError, ValueError) as error:
                print(f"{code}\tERROR: {error}", file=sys.stderr)
                exit_status = 1
                continue
            print(address)
        return exit_status

    def _locate(self, codec: AddressCodec, addresses: list[str], crs: GeodeticCrs) -> int:
        exit_status = 0
        for address in addresses:
            try:
                location = codec.locate(address, crs)
            except (LookupError, ValueError) as error:
                print(f"{address}\tERROR: {error}", file=sys.stderr)
                exit_status = 1
                continue
            print(
                "\t".join(
                    [
                        str(location.code),
                        str(location.located_code),
                        location.level.name,
                        f"{location.coordinate.latitude.degree[0]:.9f}",
                        f"{location.coordinate.longitude.degree[0]:.9f}",
                        str(location.crs),
                    ]
                )
            )
        return exit_status

    def _build_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            prog="address-codec-jp",
            description="Convert Japanese addresses to and from address codes.",
        )
        _ = parser.add_argument(
            "--database", default="towns.sqlite3", help="SQLite town database path."
        )
        subparsers = parser.add_subparsers(dest="command", required=True)

        import_parser = subparsers.add_parser(
            Command.IMPORT.value, help="Import the Address Base Registry town master."
        )
        _ = import_parser.add_argument("source", help="mt_town_all.csv or its ZIP archive.")

        encode_parser = subparsers.add_parser(Command.ENCODE.value, help="Address to code.")
        _ = encode_parser.add_argument("addresses", nargs="+", help="Addresses to encode.")

        decode_parser = subparsers.add_parser(Command.DECODE.value, help="Code to address.")
        _ = decode_parser.add_argument("codes", nargs="+", help="Address codes to decode.")
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

        positions_parser = subparsers.add_parser(
            Command.IMPORT_POSITIONS.value,
            help="Import position datasets and block, residence, or parcel masters.",
        )
        _ = positions_parser.add_argument(
            "sources", nargs="+", help="Registry CSV files or their ZIP archives."
        )

        locate_parser = subparsers.add_parser(
            Command.LOCATE.value, help="Address to representative point."
        )
        _ = locate_parser.add_argument("addresses", nargs="+", help="Addresses to locate.")
        _ = locate_parser.add_argument(
            "--crs",
            choices=[crs.name.lower() for crs in GeodeticCrs],
            default=GeodeticCrs.JGD2011.name.lower(),
        )
        return parser
