from dataclasses import dataclass
from typing import ClassVar, Self

from address_codec_jp.address.lot_system import LotSystem


@dataclass(frozen=True, slots=True)
class LotNumber:
    """
    Lot numbers that follow the town name, and the numbering system they belong to.

    A town numbered by residence indication keeps its land parcel numbers as well, so the
    same numbers can name a residence and a different parcel; ``system`` tells them apart.

    In residence indication addresses the numbers are the ``番`` (block), the ``号``
    (residence), and a branch of the residence such as the ``4`` of ``2番3-4号``. In land
    parcel addresses they are the ``番地`` (parcel), its branch, and the branch of the
    branch, such as ``124番地1の1``.

    Parameters
    ----------
    block : int | None
        First number (``番`` or ``番地``). ``None`` when the address ends at the town.
    residence : int | None
        Second number (``号`` or parcel branch). ``None`` when not specified.
    branch : int | None
        Third number. ``None`` when not specified.
    system : LotSystem | None
        Numbering system of the numbers. Required with numbers, and ``None`` without.

    Raises
    ------
    ValueError
        If a number is not positive or exceeds ``MAX_NUMBER``, a number is given without
        the one before it, or ``system`` is given exactly when no number is.
    """

    MAX_NUMBER: ClassVar[int] = 999_999_999

    block: int | None = None
    residence: int | None = None
    branch: int | None = None
    system: LotSystem | None = None

    def __post_init__(self) -> None:
        if self.block is None and self.residence is not None:
            raise ValueError("A residence number requires a block number.")
        if self.residence is None and self.branch is not None:
            raise ValueError("A branch number requires a residence number.")
        for number in (self.block, self.residence, self.branch):
            if number is not None and number <= 0:
                raise ValueError(f"Lot numbers must be positive, got {number}.")
            if number is not None and number > self.MAX_NUMBER:
                raise ValueError(f"Lot numbers must not exceed {self.MAX_NUMBER}, got {number}.")
        if (self.block is None) != (self.system is None):
            raise ValueError("A numbering system is given exactly when lot numbers are.")

    @classmethod
    def of(cls, numbers: list[int], system: LotSystem) -> Self:
        """
        Build lot numbers from a list of numbers.

        Parameters
        ----------
        numbers : list[int]
            Zero to three numbers, in order from block to branch.
        system : LotSystem
            Numbering system of the numbers. Ignored when ``numbers`` is empty.

        Returns
        -------
        Self
            Lot numbers.

        Raises
        ------
        ValueError
            If more than three numbers are given or a number is out of range.
        """
        if len(numbers) > 3:
            raise ValueError(f"At most three lot numbers are allowed, got {numbers}.")
        padded = [*numbers, None, None, None]
        return cls(
            block=padded[0],
            residence=padded[1],
            branch=padded[2],
            system=system if numbers else None,
        )

    @property
    def numbers(self) -> list[int]:
        """
        Specified numbers in order from block to branch.

        Returns
        -------
        list[int]
            Zero to three numbers.
        """
        return [
            number for number in (self.block, self.residence, self.branch) if number is not None
        ]

    @property
    def is_land_parcel(self) -> bool:
        """
        Tell whether the numbers are land parcel numbers.

        Returns
        -------
        bool
            ``True`` when ``system`` is ``LotSystem.LAND_PARCEL``.
        """
        return self.system is LotSystem.LAND_PARCEL

    def with_system(self, system: LotSystem) -> Self:
        """
        Read the same numbers in another numbering system.

        Parameters
        ----------
        system : LotSystem
            Numbering system to use.

        Returns
        -------
        Self
            Lot numbers with ``system``, or these empty numbers unchanged.
        """
        if not self.numbers:
            return self
        return type(self)(
            block=self.block, residence=self.residence, branch=self.branch, system=system
        )

    def truncated(self, count: int) -> Self:
        """
        Keep only the leading numbers.

        Parameters
        ----------
        count : int
            Number of numbers to keep.

        Returns
        -------
        Self
            Lot numbers with at most ``count`` numbers, in the same numbering system.
        """
        numbers = self.numbers[: max(count, 0)]
        if self.system is None:
            return self
        return type(self).of(numbers, self.system)
