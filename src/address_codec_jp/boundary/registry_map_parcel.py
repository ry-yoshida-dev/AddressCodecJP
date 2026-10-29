from dataclasses import dataclass

from address_codec_jp.domain.area_shape import AreaShape


@dataclass(frozen=True, slots=True)
class RegistryMapParcel:
    """
    Land parcel of a registry office map.

    Parameters
    ----------
    municipality_name : str
        Name of the municipality, such as ``千代田区``.
    oaza_name : str
        Name of the oaza.
    chome_name : str
        Name of the chome, such as ``４丁目``, or an empty string.
    lot_text : str
        Parcel number as written in the map, such as ``25-1``.
    shape : AreaShape
        Shape of the parcel on JGD2011.
    """

    municipality_name: str
    oaza_name: str
    chome_name: str
    lot_text: str
    shape: AreaShape
