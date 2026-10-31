from address_codec_jp.address import Address, AddressCode, AddressLevel
from address_codec_jp.database.storage.town_repository import TownRepository


class AddressDirectory:
    """
    Lookup of the registered areas of address codes and of the areas directly under them.

    Parameters
    ----------
    towns : TownRepository
        Imported prefectures, municipalities, and towns.
    """

    def __init__(self, towns: TownRepository) -> None:
        self._towns: TownRepository = towns

    def resolve(self, code: AddressCode) -> Address:
        """
        Look up the registered areas of an address code.

        Parameters
        ----------
        code : AddressCode
            Address code to look up.

        Returns
        -------
        Address
            Prefecture, municipality, town, and lot numbers of the code.

        Raises
        ------
        ValueError
            If lot numbers are attached to an oaza that takes them only under a chome.
        AddressNotFoundError
            If the area of the code is not registered.
        """
        if code.machiaza_id is not None:
            return Address.for_town(self._towns.get_town(code.lg_code, code.machiaza_id), code.lot)
        if code.level is AddressLevel.PREFECTURE:
            return Address(prefecture=self._towns.get_prefecture(code.prefecture_code))
        municipality = self._towns.get_municipality(code.lg_code)
        return Address(prefecture=municipality.prefecture, municipality=municipality)

    def list_children(self, code: AddressCode) -> list[Address]:
        """
        List the registered areas whose ``AddressCode.parent`` is a code.

        Parameters
        ----------
        code : AddressCode
            Prefecture, municipality, or town code.

        Returns
        -------
        list[Address]
            Child areas ordered by code. Empty for a chome or koaza.

        Raises
        ------
        ValueError
            If the code has lot numbers.
        AddressNotFoundError
            If the area of the code is not registered.
        """
        address = self.resolve(code)
        if address.lot.numbers:
            raise ValueError(f"Areas under lot numbers are not listed, got {address.code}.")
        if address.town is not None:
            if not address.code.is_oaza:
                return []
            return [Address.for_town(town) for town in self._towns.list_oaza_members(address.town)]
        if address.municipality is not None:
            return [
                Address.for_town(town) for town in self._towns.list_top_towns(address.municipality)
            ]
        return [
            Address(prefecture=municipality.prefecture, municipality=municipality)
            for municipality in self._towns.list_prefecture_municipalities(address.prefecture.code)
        ]

    def list_by_postal_code(self, postal_code: str) -> list[Address]:
        """
        List the towns registered with a postal code.

        Parameters
        ----------
        postal_code : str
            Seven-digit postal code.

        Returns
        -------
        list[Address]
            Town-level addresses ordered by code.
        """
        return [
            Address.for_town(town) for town in self._towns.list_towns_by_postal_code(postal_code)
        ]
