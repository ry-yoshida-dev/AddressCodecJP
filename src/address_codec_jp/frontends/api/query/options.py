from dataclasses import dataclass, field

from geo_coordinate import GeodeticCrs

from address_codec_jp.text.formatting import AddressFormat


@dataclass(frozen=True, slots=True)
class QueryOptions:
    """
    Options of a query; each operation uses those that apply to it.

    Parameters
    ----------
    address_format : AddressFormat
        Format of decoded addresses.
    is_lot_verified : bool
        Whether encoded lot numbers must be registered.
    crs : GeodeticCrs
        Datum of input and output coordinates.
    max_distance_meters : float
        Largest distance to the nearest address.
    is_parcel_included : bool
        Whether land parcels are listed besides towns at a coordinate.
    is_geometry_included : bool
        Whether shapes are written as GeoJSON geometries.
    """

    address_format: AddressFormat = field(default_factory=AddressFormat)
    is_lot_verified: bool = False
    crs: GeodeticCrs = GeodeticCrs.JGD2011
    max_distance_meters: float = 1000.0
    is_parcel_included: bool = False
    is_geometry_included: bool = True
