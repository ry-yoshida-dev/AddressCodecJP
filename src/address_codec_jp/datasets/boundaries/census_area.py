from dataclasses import dataclass

from address_codec_jp.geometry import AreaShape


@dataclass(frozen=True, slots=True)
class CensusArea:
    """
    Town of the census boundary data.

    Parameters
    ----------
    key_code : str
        Census code of the area (KEY_CODE).
    address : str
        Prefecture, municipality, and area names, such as ``東京都千代田区丸の内一丁目``.
    town_name : str
        Area name at the end of ``address`` (S_NAME), such as ``丸の内一丁目``.
    shape : AreaShape
        Shape of the area on JGD2011.
    """

    key_code: str
    address: str
    town_name: str
    shape: AreaShape
