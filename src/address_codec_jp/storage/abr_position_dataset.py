from __future__ import annotations

from collections.abc import Sequence
from enum import Enum


class AbrPositionDataset(Enum):
    """
    Address Base Registry datasets used to locate addresses.

    Each value is the file name prefix the registry publishes the dataset under.

    Attributes
    ----------
    AREA_POSITION
        Representative points of prefectures or municipalities
        (都道府県・市区町村マスター位置参照拡張).
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

    AREA_POSITION = "mt_pref_pos / mt_city_pos"
    TOWN_POSITION = "mt_town_pos"
    BLOCK = "mt_rsdtdsp_blk"
    BLOCK_POSITION = "mt_rsdtdsp_blk_pos"
    RESIDENCE = "mt_rsdtdsp_rsdt"
    RESIDENCE_POSITION = "mt_rsdtdsp_rsdt_pos"
    PARCEL = "mt_parcel"
    PARCEL_POSITION = "mt_parcel_pos"

    @classmethod
    def detect(cls, header: Sequence[str]) -> AbrPositionDataset:
        """
        Identify a dataset by its CSV header.

        Parameters
        ----------
        header : Sequence[str]
            Column names of the file.

        Returns
        -------
        AbrPositionDataset
            Dataset the header belongs to.

        Raises
        ------
        ValueError
            If the header belongs to none of the datasets, such as the town master.
        """
        columns = set(header)
        is_position = "rep_lon" in columns
        if "prc_id" in columns:
            return cls.PARCEL_POSITION if is_position else cls.PARCEL
        if "rsdt_id" in columns:
            return cls.RESIDENCE_POSITION if is_position else cls.RESIDENCE
        if "blk_id" in columns:
            return cls.BLOCK_POSITION if is_position else cls.BLOCK
        if is_position:
            return cls.TOWN_POSITION if "machiaza_id" in columns else cls.AREA_POSITION
        raise ValueError(
            "Not a position dataset of the Address Base Registry. Expected one of: "
            + ", ".join(dataset.value for dataset in cls)
            + "."
        )

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
            case AbrPositionDataset.AREA_POSITION:
                return ("lg_code", *point_columns)
            case AbrPositionDataset.TOWN_POSITION:
                return ("lg_code", "machiaza_id", "rsdt_addr_flg", *point_columns)
            case AbrPositionDataset.BLOCK:
                return ("lg_code", "machiaza_id", "blk_id", "blk_num", "ablt_date")
            case AbrPositionDataset.BLOCK_POSITION:
                return ("lg_code", "machiaza_id", "blk_id", *point_columns)
            case AbrPositionDataset.RESIDENCE:
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
            case AbrPositionDataset.RESIDENCE_POSITION:
                return ("lg_code", "machiaza_id", "blk_id", "rsdt_id", "rsdt2_id", *point_columns)
            case AbrPositionDataset.PARCEL:
                return (
                    "lg_code",
                    "machiaza_id",
                    "prc_id",
                    "prc_num1",
                    "prc_num2",
                    "prc_num3",
                    "ablt_date",
                )
            case AbrPositionDataset.PARCEL_POSITION:
                return ("lg_code", "machiaza_id", "prc_id", *point_columns)
