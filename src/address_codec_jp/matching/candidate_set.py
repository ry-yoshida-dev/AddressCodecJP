from dataclasses import dataclass

from address_codec_jp.domain.town import Town


@dataclass(frozen=True, slots=True)
class CandidateSet:
    """
    Towns compatible with one way of reading the address so far.

    Parameters
    ----------
    towns : list[Town]
        Candidate towns.
    remainder : str
        Normalized text not yet consumed.
    penalty : int
        Accumulated ``MatchTier.penalty`` of the name comparisons used so far.
    split_digit_count : int
        Digits that names consumed right before a number in the remainder, such as the
        ``1`` of koaza ``１`` read from ``112番`` or the ``12`` of koaza ``１２`` read
        from ``12-3``. Such digits do not count as
        explained by names.
    """

    towns: list[Town]
    remainder: str
    penalty: int
    split_digit_count: int = 0
