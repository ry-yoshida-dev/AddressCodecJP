from dataclasses import dataclass

from address_codec_jp.address import Municipality


@dataclass(frozen=True, slots=True)
class MunicipalityMatch:
    """
    Municipalities whose name starts a normalized address.

    Parameters
    ----------
    name : str
        Matched part of the normalized address, such as ``府中市`` or ``横浜市``.
    municipalities : list[Municipality]
        Municipalities sharing the name, ordered by local government code. More than one
        when the prefecture or the ward of a designated city is omitted.
    remainder : str
        Normalized text following the municipality name.
    is_ward_omitted : bool
        ``True`` when the name is a designated city written without its ward, so that a
        town name must identify the ward.
    """

    name: str
    municipalities: list[Municipality]
    remainder: str
    is_ward_omitted: bool

    @property
    def is_town_required(self) -> bool:
        """
        Tell whether a town name must identify the municipality.

        Returns
        -------
        bool
            ``True`` when the ward is omitted or several municipalities share the name.
        """
        return self.is_ward_omitted or len(self.municipalities) > 1
