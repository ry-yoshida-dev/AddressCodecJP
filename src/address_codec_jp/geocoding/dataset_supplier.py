from collections.abc import Iterable
from typing import Protocol


class DatasetSupplier(Protocol):
    """Provider of the per-municipality datasets that geocoding adds before a lookup."""

    def ensure_lots(self, lg_codes: Iterable[str]) -> None:
        """
        Add the blocks, residences, and land parcels of municipalities unless already added.

        Parameters
        ----------
        lg_codes : Iterable[str]
            Six-digit local government codes; prefecture codes are skipped.
        """
        ...

    def ensure_areas(self, lg_codes: Iterable[str], *, is_parcel_included: bool) -> None:
        """
        Add the town boundaries, and optionally the land parcel maps, of municipalities.

        Parameters
        ----------
        lg_codes : Iterable[str]
            Six-digit local government codes; prefecture codes are skipped.
        is_parcel_included : bool
            Whether the land parcel maps are added besides the town boundaries.
        """
        ...
