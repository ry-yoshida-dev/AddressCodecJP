from dataclasses import dataclass

from address_codec_jp.address import AddressCode
from address_codec_jp.results.address_location import AddressLocation


@dataclass(frozen=True, slots=True)
class NearestAddress:
    """
    Address whose representative point is nearest to a coordinate.

    Parameters
    ----------
    location : AddressLocation
        Code and representative point of the address.
    distance_meters : float
        Great-circle distance from the searched coordinate to the point.
    """

    location: AddressLocation
    distance_meters: float

    @property
    def code(self) -> AddressCode:
        """
        Code of the nearest address.

        Returns
        -------
        AddressCode
            Code of a block, residence, parcel, or town.
        """
        return self.location.code
