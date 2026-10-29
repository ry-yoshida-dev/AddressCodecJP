from dataclasses import dataclass

from address_codec_jp.domain.address_code import AddressCode
from address_codec_jp.domain.area_shape import AreaShape
from address_codec_jp.domain.area_source import AreaSource


@dataclass(frozen=True, slots=True)
class AreaRecord:
    """
    Stored shape of an address.

    Parameters
    ----------
    code : AddressCode
        Town code for a census boundary, or code with parcel numbers for a registry map.
    source : AreaSource
        Dataset the shape is taken from.
    shape : AreaShape
        Shape on JGD2011.
    """

    code: AddressCode
    source: AreaSource
    shape: AreaShape
