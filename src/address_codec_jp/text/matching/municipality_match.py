from dataclasses import dataclass

from address_codec_jp.address import Municipality


@dataclass(frozen=True, slots=True)
class MunicipalityMatch:
    """
    Municipalities whose name starts a normalized address.

    Parameters
    ----------
    name : str
        Matched part of the normalized address, such as ``府中市`` or ``横浜市``. Empty when
        the address starts with a town name.
    municipalities : list[Municipality]
        Municipalities sharing the name, ordered by local government code. More than one
        when the prefecture, the city or ward of a designated city, or the whole
        municipality name is omitted.
    remainder : str
        Normalized text following the municipality name.
    is_name_abbreviated : bool
        ``True`` when the name is a designated city written without its ward, or the
        address starts with a town name, so that a town name must identify the
        municipality.
    """

    name: str
    municipalities: list[Municipality]
    remainder: str
    is_name_abbreviated: bool

    @property
    def is_town_required(self) -> bool:
        """
        Tell whether a town name must identify the municipality.

        Returns
        -------
        bool
            ``True`` when the name is abbreviated or several municipalities share the name.
        """
        return self.is_name_abbreviated or len(self.municipalities) > 1
