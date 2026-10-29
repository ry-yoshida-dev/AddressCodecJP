from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LotNumber:
    """
    Block and residence numbers that follow the town name.

    In residence indication addresses these are the ``番`` and ``号`` numbers.
    In land parcel addresses they are the ``番地`` number and its branch number.

    Parameters
    ----------
    block : int | None
        First number (``番`` or ``番地``). ``None`` when the address ends at the town.
    residence : int | None
        Second number (``号`` or branch number). ``None`` when not specified.

    Raises
    ------
    ValueError
        If a number is not positive, or a residence is given without a block.
    """

    block: int | None = None
    residence: int | None = None

    def __post_init__(self) -> None:
        if self.block is None and self.residence is not None:
            raise ValueError("A residence number requires a block number.")
        for number in (self.block, self.residence):
            if number is not None and number <= 0:
                raise ValueError(f"Lot numbers must be positive, got {number}.")

    @property
    def numbers(self) -> list[int]:
        """
        Specified numbers in order from block to residence.

        Returns
        -------
        list[int]
            Zero, one, or two numbers.
        """
        return [number for number in (self.block, self.residence) if number is not None]
