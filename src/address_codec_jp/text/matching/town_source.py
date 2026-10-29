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
