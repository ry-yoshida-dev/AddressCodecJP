import bisect
from typing import ClassVar


class DesignatedCity:
    """
    Local government codes of the designated cities (政令指定都市) and of their wards.

    The Address Base Registry records the towns of a designated city under its wards
    only, so the city itself is known here by code. A designated city takes a code in
    the ``1xx`` range of its prefecture, and its wards take the codes that follow it up
    to the next designated city or the end of that range.

    Attributes
    ----------
    CODES : tuple[str, ...]
        Local government codes of the designated cities, in ascending order.
    """

    CODES: ClassVar[tuple[str, ...]] = (
        "011002",  # 札幌市
        "041009",  # 仙台市
        "111007",  # さいたま市
        "121002",  # 千葉市
        "141003",  # 横浜市
        "141305",  # 川崎市
        "141500",  # 相模原市
        "151009",  # 新潟市
        "221007",  # 静岡市
        "221309",  # 浜松市
        "231002",  # 名古屋市
        "261009",  # 京都市
        "271004",  # 大阪市
        "271403",  # 堺市
        "281000",  # 神戸市
        "331007",  # 岡山市
        "341002",  # 広島市
        "401005",  # 北九州市
        "401307",  # 福岡市
        "431001",  # 熊本市
    )

    @classmethod
    def is_code(cls, lg_code: str) -> bool:
        """
        Tell whether a local government code denotes a designated city.

        Parameters
        ----------
        lg_code : str
            Six-digit local government code.

        Returns
        -------
        bool
            ``True`` for the city itself, ``False`` for its wards.
        """
        return lg_code in cls.CODES

    @classmethod
    def find_code(cls, lg_code: str) -> str | None:
        """
        Find the designated city that a ward belongs to.

        Parameters
        ----------
        lg_code : str
            Six-digit local government code.

        Returns
        -------
        str | None
            Local government code of the city, or ``None`` when ``lg_code`` is not a
            ward of a designated city.
        """
        if lg_code[2] != "1" or lg_code in cls.CODES:
            return None
        index = bisect.bisect_right(cls.CODES, lg_code) - 1
        if index < 0 or cls.CODES[index][:2] != lg_code[:2]:
            return None
        return cls.CODES[index]

    @classmethod
    def ward_code_bounds(cls, lg_code: str) -> tuple[str, str]:
        """
        Give the range of the local government codes of a designated city's wards.

        Parameters
        ----------
        lg_code : str
            Six-digit local government code of a designated city.

        Returns
        -------
        tuple[str, str]
            Exclusive lower and upper bounds: every ward's code compares greater than
            the first and less than the second.

        Raises
        ------
        ValueError
            If ``lg_code`` is not a designated city.
        """
        if not cls.is_code(lg_code):
            raise ValueError(f"{lg_code} is not a designated city.")
        index = cls.CODES.index(lg_code)
        following = cls.CODES[index + 1] if index + 1 < len(cls.CODES) else ""
        if following[:2] == lg_code[:2]:
            return lg_code, following
        return lg_code, lg_code[:2] + "2"
