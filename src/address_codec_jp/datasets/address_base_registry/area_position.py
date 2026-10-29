from dataclasses import dataclass

from address_codec_jp.geometry import RepresentativePoint


@dataclass(frozen=True, slots=True)
class AreaPosition:
    """
    Representative point of a prefecture or municipality.

    Parameters
    ----------
    lg_code : str
        Six-digit local government code of the prefecture or municipality.
    point : RepresentativePoint
        Published representative point.
    """

    lg_code: str
    point: RepresentativePoint
