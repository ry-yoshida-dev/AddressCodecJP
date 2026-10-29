from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from address_codec_jp.api.format_parameters import FormatParameters


class BatchRequest(BaseModel):
    """Body of a batch request: one operation applied to many inputs."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", populate_by_name=True)

    operation: str = Field(
        description="encode, decode, locate, locate_code, nearest, postal, area, "
        + "area_code, or areas_at."
    )
    inputs: list[str] = Field(description="Addresses, codes, postal codes, or coordinates.")
    is_lot_verified: bool = Field(default=False, alias="verify_lot")
    crs: str = Field(default="jgd2011", description="tokyo, jgd2000, jgd2011, or wgs84.")
    max_distance_meters: float = Field(default=1000.0, gt=0, alias="max_distance")
    is_parcel_included: bool = Field(default=False, alias="parcels")
    is_geometry_included: bool = Field(default=False, alias="geometry")
    address_format: FormatParameters = Field(default_factory=FormatParameters, alias="format")
