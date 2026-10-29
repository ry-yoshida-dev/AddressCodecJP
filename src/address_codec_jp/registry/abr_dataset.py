from __future__ import annotations

from collections.abc import Sequence
from enum import Enum

from address_codec_jp.domain.address_code import AddressCode
from address_codec_jp.errors.registry_format_error import RegistryFormatError
from address_codec_jp.registry.distribution_scope import DistributionScope


class AbrDataset(Enum):
    """
    Address Base Registry datasets that can be downloaded and imported.

    Each value is the directory and file name prefix the registry publishes the dataset
    under.

    Attributes
    ----------
    TOWN
        Town master (町字マスター).
    PREFECTURE_POSITION
        Representative points of prefectures (都道府県マスター位置参照拡張).
    MUNICIPALITY_POSITION
        Representative points of municipalities (市区町村マスター位置参照拡張).
    TOWN_POSITION
        Representative points of towns (町字マスター位置参照拡張).
    BLOCK
        Block numbers of residence indication (住居表示-街区マスター).
    BLOCK_POSITION
        Representative points of blocks (住居表示-街区マスター位置参照拡張).
    RESIDENCE
        Residence numbers of residence indication (住居表示-住居マスター).
    RESIDENCE_POSITION
        Representative points of residences (住居表示-住居マスター位置参照拡張).
    PARCEL
        Land parcel numbers (地番マスター).
    PARCEL_POSITION
        Representative points of land parcels (地番マスター位置参照拡張).
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

    @classmethod
    def detect(cls, header: Sequence[str], first_row: Sequence[str] | None) -> AbrDataset:
        """
        Identify a dataset by its CSV header.

        Prefecture and municipality points share one header, so they are told apart by
        the local government code of the first row.

        Parameters
        ----------
        header : Sequence[str]
            Column names of the file.
        first_row : Sequence[str] | None
            First data row, or ``None`` when the file has no data rows.

        Returns
        -------
        AbrDataset
            Dataset the file belongs to.

        Raises
        ------
        RegistryFormatError
            If the header belongs to none of the datasets, or a file of prefecture or
            municipality points has no row to tell which it is.
        """
        columns = set(header)
        is_position = "rep_lon" in columns
        if "prc_id" in columns:
            return cls.PARCEL_POSITION if is_position else cls.PARCEL
        if "rsdt_id" in columns:
            return cls.RESIDENCE_POSITION if is_position else cls.RESIDENCE
        if "blk_id" in columns:
            return cls.BLOCK_POSITION if is_position else cls.BLOCK
        if is_position and "machiaza_id" in columns:
            return cls.TOWN_POSITION
        if is_position and "lg_code" in columns:
            return cls._detect_area_position(header, first_row)
        if {"machiaza_id", "oaza_cho"} <= columns:
            return cls.TOWN
        raise RegistryFormatError(
            "Not a dataset of the Address Base Registry. Expected one of: "
            + ", ".join(dataset.value for dataset in cls)
            + "."
        )

    @classmethod
    def _detect_area_position(
        cls, header: Sequence[str], first_row: Sequence[str] | None
    ) -> AbrDataset:
        lg_code_index = list(header).index("lg_code")
        if first_row is None or len(first_row) <= lg_code_index:
            raise RegistryFormatError(
                "A file of prefecture or municipality points needs a data row to tell which "
                + "it holds."
            )
        if AddressCode.is_prefecture_code(first_row[lg_code_index].zfill(6)):
            return cls.PREFECTURE_POSITION
        return cls.MUNICIPALITY_POSITION

    @property
    def is_position_related(self) -> bool:
        """
        Tell whether the dataset holds points or the lot numbers that points are keyed by.

        Returns
        -------
        bool
            ``False`` only for the town master.
        """
        return self is not AbrDataset.TOWN

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
                AbrDataset.TOWN | AbrDataset.PREFECTURE_POSITION | AbrDataset.MUNICIPALITY_POSITION
            ):
                return DistributionScope.NATIONWIDE
            case (
                AbrDataset.TOWN_POSITION
                | AbrDataset.BLOCK
                | AbrDataset.BLOCK_POSITION
                | AbrDataset.RESIDENCE
                | AbrDataset.RESIDENCE_POSITION
            ):
                return DistributionScope.PREFECTURE
            case AbrDataset.PARCEL | AbrDataset.PARCEL_POSITION:
                return DistributionScope.MUNICIPALITY

    @property
    def required_columns(self) -> tuple[str, ...]:
        """
        Columns read from the dataset.

        Returns
        -------
        tuple[str, ...]
            Column names that must be present in the header.
        """
        point_columns = ("rep_lon", "rep_lat", "rep_srid")
        match self:
            case AbrDataset.TOWN:
                return (
                    "lg_code",
                    "machiaza_id",
                    "pref",
                    "county",
                    "city",
                    "ward",
                    "oaza_cho",
                    "chome",
                    "koaza",
                    "pref_kana",
                    "county_kana",
                    "city_kana",
                    "ward_kana",
                    "oaza_cho_kana",
                    "chome_kana",
                    "koaza_kana",
                    "rsdt_addr_flg",
                    "post_code",
                    "ablt_date",
                )
            case AbrDataset.PREFECTURE_POSITION | AbrDataset.MUNICIPALITY_POSITION:
                return ("lg_code", *point_columns)
            case AbrDataset.TOWN_POSITION:
                return ("lg_code", "machiaza_id", "rsdt_addr_flg", *point_columns)
            case AbrDataset.BLOCK:
                return ("lg_code", "machiaza_id", "blk_id", "blk_num", "ablt_date")
            case AbrDataset.BLOCK_POSITION:
                return ("lg_code", "machiaza_id", "blk_id", *point_columns)
            case AbrDataset.RESIDENCE:
                return (
                    "lg_code",
                    "machiaza_id",
                    "blk_id",
                    "rsdt_id",
                    "rsdt2_id",
                    "blk_num",
                    "rsdt_num",
                    "rsdt_num2",
                    "ablt_date",
                )
            case AbrDataset.RESIDENCE_POSITION:
                return ("lg_code", "machiaza_id", "blk_id", "rsdt_id", "rsdt2_id", *point_columns)
            case AbrDataset.PARCEL:
                return (
                    "lg_code",
                    "machiaza_id",
                    "prc_id",
                    "prc_num1",
                    "prc_num2",
                    "prc_num3",
                    "ablt_date",
                )
            case AbrDataset.PARCEL_POSITION:
                return ("lg_code", "machiaza_id", "prc_id", *point_columns)
