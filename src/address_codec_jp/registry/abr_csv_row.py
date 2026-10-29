from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AbrCsvRow:
    """
    Data row of a registry CSV file, reduced to the columns its dataset requires.

    Parameters
    ----------
    number : int
        Line number of the row in the file, counting the header as line 1.
    values : dict[str, str]
        Values of the required columns by column name.
    """

    number: int
    values: dict[str, str]
