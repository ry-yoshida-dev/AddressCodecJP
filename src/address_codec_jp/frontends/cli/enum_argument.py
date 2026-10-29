import argparse
from enum import Enum

from address_codec_jp.frontends.serialization import EnumName


class EnumArgument[EnumType: Enum]:
    """
    Converter of a command line value to a member of an enum, by member name.

    Values are matched case-insensitively, so ``--crs wgs84`` gives ``GeodeticCrs.WGS84``.

    Parameters
    ----------
    enum_type : type[EnumType]
        Enum whose members are accepted.
    """

    def __init__(self, enum_type: type[EnumType]) -> None:
        self._enum_name: EnumName[EnumType] = EnumName(enum_type)

    @property
    def metavar(self) -> str:
        """
        Usage text listing the accepted values.

        Returns
        -------
        str
            Lowercase member names, such as ``{arabic,kanji}``.
        """
        return "{" + ",".join(self._enum_name.choices) + "}"

    def __call__(self, text: str) -> EnumType:
        """
        Convert a value.

        Parameters
        ----------
        text : str
            Member name in any case.

        Returns
        -------
        EnumType
            Matching member.

        Raises
        ------
        argparse.ArgumentTypeError
            If no member has the name.
        """
        if not self._enum_name.is_member(text):
            raise argparse.ArgumentTypeError(f"invalid choice {text!r}; choose from {self.metavar}")
        return self._enum_name.parse(text)
