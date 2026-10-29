from enum import Enum

from address_codec_jp.download.distribution_scope import DistributionScope


class RegistryFile(Enum):
    """
    Downloadable dataset of the Address Base Registry.

    Each value is the directory and file name prefix of the dataset on the download site.

    Attributes
    ----------
    TOWN
        Town master (町字マスター).
    PREFECTURE_POSITION
        Representative points of prefectures.
    MUNICIPALITY_POSITION
        Representative points of municipalities.
    TOWN_POSITION
        Representative points of towns.
    BLOCK
        Block numbers of residence indication.
    BLOCK_POSITION
        Representative points of blocks.
    RESIDENCE
        Residence numbers of residence indication.
    RESIDENCE_POSITION
        Representative points of residences.
    PARCEL
        Land parcel numbers.
    PARCEL_POSITION
        Representative points of land parcels.
    """

    TOWN = "mt_town"
    PREFECTURE_POSITION = "mt_pref_pos"
    MUNICIPALITY_POSITION = "mt_city_pos"
    TOWN_POSITION = "mt_town_pos"
    BLOCK = "mt_rsdtdsp_blk"
    BLOCK_POSITION = "mt_rsdtdsp_blk_pos"
    RESIDENCE = "mt_rsdtdsp_rsdt"
    RESIDENCE_POSITION = "mt_rsdtdsp_rsdt_pos"
    PARCEL = "mt_parcel"
    PARCEL_POSITION = "mt_parcel_pos"

    @property
    def scope(self) -> DistributionScope:
        """
        Area unit of the distributed files.

        Returns
        -------
        DistributionScope
            Nationwide, per prefecture, or per municipality.
        """
        match self:
            case (
                RegistryFile.TOWN
                | RegistryFile.PREFECTURE_POSITION
                | RegistryFile.MUNICIPALITY_POSITION
            ):
                return DistributionScope.NATIONWIDE
            case (
                RegistryFile.TOWN_POSITION
                | RegistryFile.BLOCK
                | RegistryFile.BLOCK_POSITION
                | RegistryFile.RESIDENCE
                | RegistryFile.RESIDENCE_POSITION
            ):
                return DistributionScope.PREFECTURE
            case RegistryFile.PARCEL | RegistryFile.PARCEL_POSITION:
                return DistributionScope.MUNICIPALITY
