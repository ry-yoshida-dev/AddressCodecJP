from dataclasses import dataclass

from address_codec_jp.domain.address_code import AddressCode
from address_codec_jp.domain.municipality import Municipality


@dataclass(frozen=True, slots=True)
class Town:
    """
    Town (町字) record of the Address Base Registry.

    Parameters
    ----------
    lg_code : str
        Six-digit local government code.
    machiaza_id : str
        Seven-digit town identifier unique within the municipality.
    prefecture_name : str
        Prefecture name.
    county_name : str
        County name, or an empty string.
    city_name : str
        City, town, village, or special ward name.
    ward_name : str
        Ward name of a designated city, or an empty string.
    oaza_name : str
        Oaza or town name (大字・町名).
    chome_name : str
        Chome name as registered, e.g. ``一丁目``, or an empty string.
    chome_number : int | None
        Numeric chome derived from ``chome_name``. ``None`` when there is no numeric chome.
    koaza_name : str
        Koaza name (小字名), or an empty string.
    is_registered : bool
        ``False`` for an oaza-level town that this library added because the registry
        lists the oaza only by chome. Such a town cannot carry lot numbers, because lot
        numbers of that oaza belong to one of its chome.

    Raises
    ------
    ValueError
        If ``lg_code`` or ``machiaza_id`` is malformed.
    """

    lg_code: str
    machiaza_id: str
    prefecture_name: str
    county_name: str
    city_name: str
    ward_name: str
    oaza_name: str
    chome_name: str
    chome_number: int | None
    koaza_name: str
    is_registered: bool = True

    def __post_init__(self) -> None:
        _ = AddressCode(lg_code=self.lg_code, machiaza_id=self.machiaza_id)

    @property
    def municipality(self) -> Municipality:
        """
        Municipality that contains this town.

        Returns
        -------
        Municipality
            Municipality built from the town's administrative names.
        """
        return Municipality(
            lg_code=self.lg_code,
            prefecture_name=self.prefecture_name,
            county_name=self.county_name,
            city_name=self.city_name,
            ward_name=self.ward_name,
        )
