import argparse

from geo_coordinate import GeodeticCrs

from address_codec_jp.datasets.download import RegistryDownloader
from address_codec_jp.frontends.cli.cache_action import CacheAction
from address_codec_jp.frontends.cli.command import Command
from address_codec_jp.frontends.cli.enum_argument import EnumArgument
from address_codec_jp.frontends.cli.output_format import OutputFormat
from address_codec_jp.text.formatting import DigitWidth, LotStyle, NumeralStyle


class ParserFactory:
    """Argument parser of the ``address-codec-jp`` command and its sub-commands."""

    def build(self) -> argparse.ArgumentParser:
        """
        Build the parser of all sub-commands.

        Returns
        -------
        argparse.ArgumentParser
            Parser that fills a ``CommandArguments`` namespace.
        """
        parser = argparse.ArgumentParser(
            prog="address-codec-jp",
            description="Convert Japanese addresses to and from address codes.",
            epilog="Exit status: 0 when every input was answered, 1 when some input failed "
            + "(each failure is written in place of its result), 2 for invalid arguments, "
            + "and 3 when the command could not run or stopped.",
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
            help="tsv with the input first on every line, or jsonl with one object per "
            + "input; both include errors in place of results.",
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

        import_area_parser = subparsers.add_parser(
            Command.IMPORT_AREA.value,
            help="Import census boundary or registry map files of one municipality.",
        )
        _ = import_area_parser.add_argument(
            "sources", nargs="+", help="Census boundary ZIP archives or registry map archives."
        )
        _ = import_area_parser.add_argument(
            "--lg-code",
            dest="lg_code",
            required=True,
            help="Six-digit local government code of the municipality the files cover.",
        )

        cache_parser = subparsers.add_parser(
            Command.CACHE.value,
            help="Show, clear, or refresh the default database in the user cache directory.",
        )
        cache_action_argument = EnumArgument(CacheAction)
        _ = cache_parser.add_argument(
            "cache_action",
            type=cache_action_argument,
            metavar=cache_action_argument.metavar,
            nargs="?",
            default=CacheAction.INFO,
            help="info (default), clear, refresh, or prepare.",
        )
        _ = cache_parser.add_argument(
            "--prefecture",
            dest="prefectures",
            action="append",
            default=[],
            metavar="CODE",
            help="prepare: two-digit code of a prefecture to prepare; repeatable.",
        )
        _ = cache_parser.add_argument(
            "--municipality",
            dest="municipalities",
            action="append",
            default=[],
            metavar="LG_CODE",
            help="prepare: six-digit code of a municipality to prepare; repeatable.",
        )
        _ = cache_parser.add_argument(
            "--no-areas",
            dest="is_area_excluded",
            action="store_true",
            help="prepare: skip the census town boundaries.",
        )
        _ = cache_parser.add_argument(
            "--parcels",
            dest="is_parcel_included",
            action="store_true",
            help="prepare: also add the registry maps of land parcels.",
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

        locate_code_parser = subparsers.add_parser(
            Command.LOCATE_CODE.value,
            parents=[query_parser, crs_parser],
            help="Code to representative point.",
        )
        _ = locate_code_parser.add_argument(
            "inputs", nargs="*", metavar="code", help="Address codes; standard input if none."
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
        children_parser = subparsers.add_parser(
            Command.CHILDREN.value,
            parents=[query_parser, format_parser],
            help="Code to the registered areas directly under it.",
        )
        _ = children_parser.add_argument(
            "inputs",
            nargs="*",
            metavar="code",
            help="Prefecture, municipality, or town codes; standard input if none.",
        )
        name_parser = subparsers.add_parser(
            Command.NAME.value,
            parents=[query_parser, format_parser],
            help="Name to every registered area that bears it.",
        )
        _ = name_parser.add_argument(
            "inputs",
            nargs="*",
            metavar="name",
            help="Names such as 府中市 or 自由が丘; standard input if none.",
        )

        area_geometry_parser = argparse.ArgumentParser(add_help=False)
        _ = area_geometry_parser.add_argument(
            "--no-geometry",
            dest="is_geometry_included",
            action="store_false",
            help="Omit the GeoJSON geometry.",
        )
        area_parser = subparsers.add_parser(
            Command.AREA.value,
            parents=[query_parser, area_geometry_parser],
            help="Address to the shape of its town or land parcel as GeoJSON on JGD2011.",
        )
        _ = area_parser.add_argument(
            "inputs", nargs="*", metavar="address", help="Addresses; standard input if none."
        )

        area_code_parser = subparsers.add_parser(
            Command.AREA_CODE.value,
            parents=[query_parser, area_geometry_parser],
            help="Code to the shape of its town or land parcel as GeoJSON on JGD2011.",
        )
        _ = area_code_parser.add_argument(
            "inputs", nargs="*", metavar="code", help="Address codes; standard input if none."
        )

        areas_at_parser = subparsers.add_parser(
            Command.AREAS_AT.value,
            parents=[query_parser, crs_parser],
            help="Coordinate to the towns, and optionally land parcels, whose shapes contain it.",
        )
        _ = areas_at_parser.add_argument(
            "inputs",
            nargs="*",
            metavar="latitude,longitude",
            help="Coordinates in decimal degrees; standard input if none.",
        )
        _ = areas_at_parser.add_argument(
            "--parcels",
            dest="is_parcel_included",
            action="store_true",
            help="Also list land parcels from the registry maps.",
        )
        _ = areas_at_parser.add_argument(
            "--geometry",
            dest="is_geometry_included",
            action="store_true",
            help="Add the GeoJSON geometries on JGD2011.",
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
