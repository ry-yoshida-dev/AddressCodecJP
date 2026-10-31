from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from address_codec_jp.address_codec import AddressCodec
from address_codec_jp.frontends.api.format_parameters import FormatParameters
from address_codec_jp.frontends.query import QueryOperation


class BatchRequest(BaseModel):
    """
    Body of a batch request: one operation applied to many inputs.

    Options default as for the GET endpoint of the operation; ``geometry`` is written
    by default for ``area`` and ``area-code`` but not for ``areas-at``.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", populate_by_name=True)

    operation: QueryOperation = Field(
        description="Operation applied to every input: " + ", ".join(QueryOperation.names()) + "."
    )
    inputs: list[str] = Field(description="Addresses, codes, postal codes, or coordinates.")
    is_lot_verified: bool = Field(default=False, alias="verify_lot")
    crs: str = Field(default="jgd2011", description="tokyo, jgd2000, jgd2011, or wgs84.")
    max_distance_meters: float = Field(
        default=AddressCodec.DEFAULT_MAX_DISTANCE_METERS, gt=0, alias="max_distance"
    )
    is_parcel_included: bool = Field(default=False, alias="parcels")
    is_geometry_included: bool | None = Field(
        default=None,
        alias="geometry",
        description="Whether GeoJSON geometries are written; by default for area and "
        + "area-code, not for areas-at.",
    )
    address_format: FormatParameters = Field(default_factory=FormatParameters, alias="format")

    def resolve_geometry(self) -> bool:
        """
        Tell whether the geometries are written.

        Returns
        -------
        bool
            ``geometry`` when given, otherwise the default of the operation.
        """
        if self.is_geometry_included is None:
            return self.operation.is_geometry_included_by_default
        return self.is_geometry_included
