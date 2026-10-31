from enum import Enum


class QueryOperation(Enum):
    """
    Query applied to one text input, shared by the command line and the web API.

    Values are the names of the batch operations, which are also the names of the
    command line sub-commands.

    Attributes
    ----------
    ENCODE
        Address to its code.
    DECODE
        Code to its address.
    LOCATE
        Address to its representative point.
    LOCATE_CODE
        Code to its representative point.
    NEAREST
        ``latitude,longitude`` to the nearest address.
    POSTAL
        Postal code to its towns.
    CHILDREN
        Code to the registered areas directly under it.
    NAME
        Name to every registered area that bears it.
    AREA
        Address to its shape.
    AREA_CODE
        Code to its shape.
    AREAS_AT
        ``latitude,longitude`` to the towns and parcels that contain it.
    """

    ENCODE = "encode"
    DECODE = "decode"
    LOCATE = "locate"
    LOCATE_CODE = "locate-code"
    NEAREST = "nearest"
    POSTAL = "postal"
    CHILDREN = "children"
    NAME = "name"
    AREA = "area"
    AREA_CODE = "area-code"
    AREAS_AT = "areas-at"

    @property
    def is_geometry_included_by_default(self) -> bool:
        """
        Tell whether the operation writes GeoJSON geometries unless asked not to.

        Returns
        -------
        bool
            ``True`` for ``area`` and ``area-code``, whose shape is the result, and
            ``False`` for ``areas-at``, as for the corresponding GET endpoints.
        """
        match self:
            case QueryOperation.AREAS_AT:
                return False
            case _:
                return True

    @classmethod
    def names(cls) -> list[str]:
        """
        List the operation names.

        Returns
        -------
        list[str]
            Values in definition order.
        """
        return [operation.value for operation in cls]
