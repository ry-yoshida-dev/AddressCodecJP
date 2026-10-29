from enum import Enum


class EnumName[EnumType: Enum]:
    """
    Converter of a text value to a member of an enum, by member name.

    Names are matched case-insensitively, so ``wgs84`` gives ``GeodeticCrs.WGS84``.

    Parameters
    ----------
    enum_type : type[EnumType]
        Enum whose members are accepted.
    """

    def __init__(self, enum_type: type[EnumType]) -> None:
        self._enum_type: type[EnumType] = enum_type

    @property
    def choices(self) -> list[str]:
        """
        Accepted values.

        Returns
        -------
        list[str]
            Lowercase member names in definition order.
        """
        return [name.lower() for name in self._enum_type.__members__]

    def is_member(self, text: str) -> bool:
        """
        Tell whether a value names a member.

        Parameters
        ----------
        text : str
            Member name in any case.

        Returns
        -------
        bool
            ``True`` when ``parse`` accepts the value.
        """
        return text.upper() in self._enum_type.__members__

    def parse(self, text: str) -> EnumType:
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
        ValueError
            If no member has the name.
        """
        member = self._enum_type.__members__.get(text.upper())
        if member is None:
            choices = ",".join(self.choices)
            raise ValueError(f"Invalid choice {text!r}; choose from {{{choices}}}.")
        return member
