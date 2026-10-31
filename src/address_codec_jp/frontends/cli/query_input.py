from enum import Enum, auto


class QueryInput(Enum):
    """Kind of the positional inputs a query sub-command reads."""

    ADDRESS = auto()
    CODE = auto()
    PARENT_CODE = auto()
    COORDINATE = auto()
    POSTAL_CODE = auto()
    NAME = auto()

    @property
    def metavar(self) -> str:
        """
        Name of one input in the usage.

        Returns
        -------
        str
            Placeholder such as ``address`` or ``latitude,longitude``.
        """
        match self:
            case QueryInput.ADDRESS:
                return "address"
            case QueryInput.CODE | QueryInput.PARENT_CODE:
                return "code"
            case QueryInput.COORDINATE:
                return "latitude,longitude"
            case QueryInput.POSTAL_CODE:
                return "postal_code"
            case QueryInput.NAME:
                return "name"

    @property
    def help_text(self) -> str:
        """
        Help of the inputs, which are read from standard input when none is given.

        Returns
        -------
        str
            Description of the inputs.
        """
        match self:
            case QueryInput.ADDRESS:
                return "Addresses; standard input if none."
            case QueryInput.CODE:
                return "Address codes; standard input if none."
            case QueryInput.PARENT_CODE:
                return "Prefecture, municipality, or town codes; standard input if none."
            case QueryInput.COORDINATE:
                return "Coordinates in decimal degrees; standard input if none."
            case QueryInput.POSTAL_CODE:
                return "Postal codes such as 100-0005; standard input if none."
            case QueryInput.NAME:
                return "Names such as 府中市 or 自由が丘; standard input if none."
