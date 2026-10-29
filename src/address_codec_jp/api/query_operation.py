from enum import Enum, auto


class QueryOperation(Enum):
    """
    Query of the web API, applied to one text input.

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
    AREA
        Address to its shape.
    AREA_CODE
        Code to its shape.
    AREAS_AT
        ``latitude,longitude`` to the towns and parcels that contain it.
    """

    ENCODE = auto()
    DECODE = auto()
    LOCATE = auto()
    LOCATE_CODE = auto()
    NEAREST = auto()
    POSTAL = auto()
    AREA = auto()
    AREA_CODE = auto()
    AREAS_AT = auto()
