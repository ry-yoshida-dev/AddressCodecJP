from enum import Enum, auto


class DigitWidth(Enum):
    """
    Character width of Arabic digits in formatted output.

    The width applies to registry names as well, so ``笹津７区`` is written ``笹津7区``
    with ``HALF``. ``FULL`` also widens hyphens of lot numbers.
    """

    HALF = auto()
    FULL = auto()
