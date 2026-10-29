from enum import Enum, auto


class MatchTier(Enum):
    """
    Strictness of a name comparison, from strictest to loosest.

    Attributes
    ----------
    EXACT
        Strictly normalized names must be equal.
    UNPREFIXED
        A leading ``大字`` or ``字`` is ignored.
    FOLDED
        Prefixes are ignored and notation variants such as ``ノ``/``の`` are folded.
    """

    EXACT = auto()
    UNPREFIXED = auto()
    FOLDED = auto()

    @property
    def penalty(self) -> int:
        """
        Cost of matching at this tier; stricter tiers cost less.

        Returns
        -------
        int
            ``0`` for ``EXACT``, ``1`` for ``UNPREFIXED``, ``2`` for ``FOLDED``.
        """
        match self:
            case MatchTier.EXACT:
                return 0
            case MatchTier.UNPREFIXED:
                return 1
            case MatchTier.FOLDED:
                return 2
