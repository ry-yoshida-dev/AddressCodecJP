from dataclasses import dataclass

from address_codec_jp.domain.area_source import AreaSource


@dataclass(frozen=True, slots=True)
class AreaTarget:
    """
    Area dataset of one municipality to add to a cache.

    Parameters
    ----------
    source : AreaSource
        Dataset of the shapes.
    lg_code : str
        Six-digit local government code of the municipality.
    """

    source: AreaSource
    lg_code: str
