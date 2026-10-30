from collections.abc import Collection
from typing import Protocol

from address_codec_jp.address import Municipality, Town


class TownSource(Protocol):
    """Read access to the registered municipalities and towns that matching needs."""

    def list_municipalities(self) -> list[Municipality]:
        """
        List all municipalities.

        Returns
        -------
        list[Municipality]
            Municipalities ordered by local government code.
        """
        ...

    def list_towns(self, lg_code: str) -> list[Town]:
        """
        List the towns of a municipality.

        Parameters
        ----------
        lg_code : str
            Six-digit local government code.

        Returns
        -------
        list[Town]
            Towns ordered by town identifier. Empty for an unknown municipality.
        """
        ...

    def list_municipality_codes(self, postal_code: str) -> set[str]:
        """
        List the municipalities that have a town with a postal code.

        Parameters
        ----------
        postal_code : str
            Seven-digit postal code.

        Returns
        -------
        set[str]
            Local government codes. Empty when no town has the postal code.
        """
        ...

    def map_oaza_names(self) -> dict[str, set[str]]:
        """
        Map every oaza name to the municipalities that have a town under it.

        Returns
        -------
        dict[str, set[str]]
            Local government codes by oaza name. Towns without an oaza name are left out.
        """
        ...

    def list_town_names(self) -> set[str]:
        """
        List every oaza and koaza name.

        Returns
        -------
        set[str]
            Registry names as written. Empty names are left out.
        """
        ...

    def list_towns_named(self, names: Collection[str]) -> list[Town]:
        """
        List the towns whose oaza or koaza name is one of the names.

        Parameters
        ----------
        names : Collection[str]
            Oaza or koaza names as written in the registry.

        Returns
        -------
        list[Town]
            Towns ordered by local government code and town identifier.
        """
        ...
