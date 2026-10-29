import argparse
from enum import Enum


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
        self._enum_type: type[EnumType] = enum_type

    @property
    def metavar(self) -> str:
        """
        Usage text listing the accepted values.

        Returns
        -------
        str
            Lowercase member names, such as ``{arabic,kanji}``.
        """
        return "{" + ",".join(name.lower() for name in self._enum_type.__members__) + "}"

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
        member = self._enum_type.__members__.get(text.upper())
        if member is None:
            raise argparse.ArgumentTypeError(f"invalid choice {text!r}; choose from {self.metavar}")
        return member
