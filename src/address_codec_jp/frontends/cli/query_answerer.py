from typing import assert_never

from address_codec_jp.address_codec import AddressCodec
from address_codec_jp.errors import AddressNotFoundError, AreaNotFoundError
from address_codec_jp.frontends.cli.command import Command
from address_codec_jp.frontends.cli.command_arguments import CommandArguments
from address_codec_jp.frontends.cli.record_writer import RecordWriter
from address_codec_jp.frontends.serialization import CoordinateText, ResultSerializer
from address_codec_jp.text.formatting import AddressFormat, NameScript


class QueryAnswerer:
    """
    Answers the inputs of the query commands with a codec.

    Parameters
    ----------
    codec : AddressCodec
        Open codec that answers the queries.
    """

    def __init__(self, codec: AddressCodec) -> None:
        self._codec: AddressCodec = codec
        self._serializer: ResultSerializer = ResultSerializer(codec)
        self._coordinate_text: CoordinateText = CoordinateText()

    def answer(
        self,
        command: Command,
        namespace: CommandArguments,
        writer: RecordWriter,
        input_text: str,
    ) -> None:
        """
        Answer one input of a query command.

        Parameters
        ----------
        command : Command
            Query command such as ``encode`` or ``area-at``.
        namespace : CommandArguments
            Parsed options of the command.
        writer : RecordWriter
            Writer of the answer.
        input_text : str
            Address, code, coordinate, or postal code.

        Raises
        ------
        LookupError
            If nothing is registered for the input.
        ValueError
            If the input is malformed.
        RuntimeError
            If ``command`` is not a query command.
        """
        codec = self._codec
        serializer = self._serializer
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
                    serializer.match(address_match),
                )
            case Command.DECODE:
                fields = serializer.decoded(input_text, self._address_format(namespace))
                writer.write(input_text, [[str(fields["address"])]], fields)
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
                    serializer.location(location),
                )
            case Command.NEAREST:
                nearest = codec.find_nearest(
                    self._coordinate_text.parse(input_text), namespace.crs, namespace.max_distance
                )
                location = nearest.location
                fields = serializer.nearest(nearest)
                writer.write(
                    input_text,
                    [
                        [
                            str(nearest.code),
                            str(fields["address"]),
                            location.level.name,
                            f"{location.latitude_degrees:.9f}",
                            f"{location.longitude_degrees:.9f}",
                            f"{nearest.distance_meters:.1f}",
                            str(location.crs),
                        ]
                    ],
                    fields,
                )
            case Command.POSTAL:
                address_format = self._address_format(namespace)
                addresses = codec.list_by_postal_code(input_text)
                if not addresses:
                    raise AddressNotFoundError(f"No town is registered with {input_text!r}.")
                writer.write(
                    input_text,
                    [
                        [str(address.code), codec.decode(address.code, address_format)]
                        for address in addresses
                    ],
                    serializer.towns(addresses, address_format),
                )
            case Command.CHILDREN:
                address_format = self._address_format(namespace)
                children = codec.list_children(input_text)
                writer.write(
                    input_text,
                    [
                        [
                            str(child.code),
                            codec.decode(child.code, address_format),
                            child.code.level.name,
                        ]
                        for child in children
                    ],
                    serializer.children(children, address_format),
                )
            case Command.AREA:
                area = codec.find_area(input_text)
                writer.write(
                    input_text,
                    [
                        [
                            str(area.code),
                            str(area.located_code),
                            area.level.name,
                            serializer.source_names(area),
                            area.shape.to_geojson(),
                        ]
                    ],
                    serializer.area(area, is_geometry_included=True),
                )
            case Command.AREA_AT:
                areas = codec.find_areas_at(
                    self._coordinate_text.parse(input_text),
                    namespace.crs,
                    is_parcel_included=namespace.is_parcel_included,
                )
                if not areas:
                    raise AreaNotFoundError(f"No imported area shape contains {input_text!r}.")
                writer.write(
                    input_text,
                    [
                        [
                            str(area.code),
                            serializer.area_address(area),
                            area.level.name,
                            serializer.source_names(area),
                        ]
                        for area in areas
                    ],
                    serializer.areas(areas, is_geometry_included=True),
                )
            case (
                Command.IMPORT
                | Command.IMPORT_AREA
                | Command.DOWNLOAD
                | Command.INFO
                | Command.CACHE
            ):
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
