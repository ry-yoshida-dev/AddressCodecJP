from dataclasses import dataclass

from address_codec_jp.geometry import AreaShape


@dataclass(frozen=True, slots=True)
class CensusArea:
    """
    Small area of the census boundary data: a town, or a water area.

    Parameters
    ----------
    key_code : str
        Census code of the area (KEY_CODE).
    address : str
        Prefecture, municipality, and area names, such as ``東京都千代田区丸の内一丁目``.
    town_name : str
        Area name at the end of ``address`` (S_NAME), such as ``丸の内一丁目``; empty for
        an area the census leaves unnamed.
    shape : AreaShape
        Shape of the area on JGD2011.
    is_land : bool
        Whether the area is a town rather than a water area.
    """

    key_code: str
    address: str
    town_name: str
    shape: AreaShape
    is_land: bool
