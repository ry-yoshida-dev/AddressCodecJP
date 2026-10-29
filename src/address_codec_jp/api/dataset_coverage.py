from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Self

from address_codec_jp.caching.cache_status import CacheStatus
from address_codec_jp.domain.address_code import AddressCode
from address_codec_jp.domain.area_source import AreaSource
from address_codec_jp.errors.dataset_not_imported_error import DatasetNotImportedError
from address_codec_jp.storage.area_import import AreaImport


@dataclass(frozen=True, slots=True)
class DatasetCoverage:
    """
    Municipalities whose detailed datasets a cache holds.

    Parameters
    ----------
    lot_municipality_codes : frozenset[str]
        Municipalities whose blocks, residences, and land parcels were added.
    boundary_municipality_codes : frozenset[str]
        Municipalities whose census town boundaries were added.
    registry_map_dates : Mapping[str, date]
        Date the registry maps of each municipality were last obtained.
    """

    lot_municipality_codes: frozenset[str]
    boundary_municipality_codes: frozenset[str]
    registry_map_dates: Mapping[str, date]

    @classmethod
    def from_status(cls, status: CacheStatus, area_imports: list[AreaImport]) -> Self:
        """
        Read the coverage of a cache.

        Parameters
        ----------
        status : CacheStatus
            Result of ``DatabaseCache.describe``.
        area_imports : list[AreaImport]
            Area imports of the database, which date the registry maps.

        Returns
        -------
        Self
            Municipalities with lots, with boundaries, and the dates of their maps.
        """
        registry_map_dates: dict[str, date] = {}
        for area_import in area_imports:
            if area_import.source is AreaSource.REGISTRY_MAP:
                imported_on = area_import.imported_at.date()
                previous = registry_map_dates.get(area_import.lg_code)
                if previous is None or imported_on > previous:
                    registry_map_dates[area_import.lg_code] = imported_on
        return cls(
            lot_municipality_codes=frozenset(status.lot_municipality_codes),
            boundary_municipality_codes=frozenset(status.boundary_municipality_codes),
            registry_map_dates=registry_map_dates,
        )

    def require_lots(self, lg_code: str) -> None:
        """
        Fail unless the blocks, residences, and land parcels of an area were added.

        Parameters
        ----------
        lg_code : str
            Local government code; prefecture codes always pass.

        Raises
        ------
        DatasetNotImportedError
            If the municipality has not been prepared.
        """
        if not AddressCode.is_prefecture_code(lg_code) and (
            lg_code not in self.lot_municipality_codes
        ):
            raise DatasetNotImportedError(
                f"Blocks, residences, and land parcels of municipality {lg_code} are not "
                + "prepared on this server."
            )

    def require_boundaries(self, lg_code: str) -> None:
        """
        Fail unless the census town boundaries of an area were added.

        Parameters
        ----------
        lg_code : str
            Local government code; prefecture codes always pass.

        Raises
        ------
        DatasetNotImportedError
            If the municipality has not been prepared.
        """
        if not AddressCode.is_prefecture_code(lg_code) and (
            lg_code not in self.boundary_municipality_codes
        ):
            raise DatasetNotImportedError(
                f"Town boundaries of municipality {lg_code} are not prepared on this server."
            )
