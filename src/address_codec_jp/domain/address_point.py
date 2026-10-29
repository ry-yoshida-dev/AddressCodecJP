from dataclasses import dataclass

from address_codec_jp.domain.address_code import AddressCode
from address_codec_jp.domain.representative_point import RepresentativePoint


@dataclass(frozen=True, slots=True)
class AddressPoint:
    """
    Published representative point together with the code of its area.

    Parameters
    ----------
    code : AddressCode
        Code of the town, block, residence, or parcel.
    point : RepresentativePoint
        Representative point on its published datum.
    """

    code: AddressCode
    point: RepresentativePoint
