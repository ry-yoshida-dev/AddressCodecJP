from dataclasses import dataclass

from address_codec_jp.database.storage.area.record import AreaRecord


@dataclass(frozen=True, slots=True)
class AreaBatch:
    """
    Shapes of one area file matched to address codes, ready to be stored.

    Parameters
    ----------
    records : list[AreaRecord]
        Shapes matched to a code.
    unmatched_count : int
        Shapes skipped because they fit no address or several equally well.
    """

    records: list[AreaRecord]
    unmatched_count: int
