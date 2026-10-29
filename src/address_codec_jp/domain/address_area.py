from dataclasses import dataclass

from address_codec_jp.domain.address_code import AddressCode
from address_codec_jp.domain.address_level import AddressLevel
from address_codec_jp.domain.area_shape import AreaShape
from address_codec_jp.domain.area_source import AreaSource


@dataclass(frozen=True, slots=True)
class AddressArea:
    """
    Shape of an address.

    When no shape is published for the address itself, the shape of the nearest
    enclosing area is used, e.g. the town for a residence. An oaza or a municipality
    without a shape of its own is made of the shapes of its towns.

    Parameters
    ----------
    code : AddressCode
        Code of the requested address.
    located_code : AddressCode
        Code of the area whose shape is returned. Equal to ``code`` or one of its
        ancestors.
    shape : AreaShape
        Shape of ``located_code`` on JGD2011.
    sources : frozenset[AreaSource]
        Datasets the shape is taken from.
    """

    code: AddressCode
    located_code: AddressCode
    shape: AreaShape
    sources: frozenset[AreaSource]

    @property
    def level(self) -> AddressLevel:
        """
        Granularity of the returned shape.

        Returns
        -------
        AddressLevel
            Level of ``located_code``.
        """
        return self.located_code.level

    @property
    def is_exact(self) -> bool:
        """
        Tell whether the shape stands for the requested address itself.

        Returns
        -------
        bool
            ``True`` when no enclosing area had to be used.
        """
        return self.located_code == self.code
