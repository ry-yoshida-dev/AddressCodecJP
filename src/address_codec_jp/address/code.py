import re
import unicodedata
from dataclasses import dataclass, field
from typing import ClassVar, Self, override

from address_codec_jp.address.designated_city import DesignatedCity
from address_codec_jp.address.level import AddressLevel
from address_codec_jp.address.lot_number import LotNumber
from address_codec_jp.address.lot_system import LotSystem


@dataclass(frozen=True, slots=True)
class AddressCode:
    """
    Address code composed of a local government code, a town identifier, and lot numbers.

    The string form is ``{lg_code}[-{machiaza_id}[-[p]{block}[-{residence}[-{branch}]]]]``:

    - ``130001``: prefecture (東京都)
    - ``131067``: municipality (東京都台東区)
    - ``011002``: designated city (北海道札幌市), enclosing its wards such as ``011011``
    - ``131067-0004000``: oaza (東京都台東区浅草橋)
    - ``131067-0004001-2-3``: residence indication (浅草橋1丁目2番3号)
    - ``113247-0001000-p124-1-1``: land parcel (竹間沢124番地1の1)

    Land parcel numbers carry the ``p`` marker, because a town numbered by residence
    indication keeps its land parcels, whose numbers may coincide with residences.

    Parameters
    ----------
    lg_code : str
        Six-digit local government code including its check digit.
        Prefecture codes have ``000`` in the third to fifth digits.
    machiaza_id : str | None
        Seven-digit town identifier of the Address Base Registry.
        ``None`` for prefecture and municipality codes.
    lot : LotNumber
        Lot numbers and their numbering system. Only allowed together with
        ``machiaza_id``.

    Raises
    ------
    ValueError
        If a component is malformed, the check digit is wrong, or components are
        combined in an invalid way.
    """

    _PATTERN: ClassVar[re.Pattern[str]] = re.compile(
        r"(?P<lg_code>[0-9]{6})"
        + r"(?:-(?P<machiaza_id>[0-9]{7})"
        + r"(?:-(?P<parcel_marker>[pP])?(?P<block>[1-9][0-9]*)"
        + r"(?:-(?P<residence>[1-9][0-9]*)(?:-(?P<branch>[1-9][0-9]*))?)?)?)?"
    )
    _DASHES: ClassVar[dict[int, int]] = str.maketrans("‐‑‒–—―−ー－", "-" * 9)
    _CHECK_DIGIT_WEIGHTS: ClassVar[tuple[int, ...]] = (6, 5, 4, 3, 2)
    _OAZA_CHOME_PART: ClassVar[str] = "000"
    _ABSENT_OAZA_PART: ClassVar[str] = "0000"
    _PARCEL_MARKER: ClassVar[str] = "p"

    lg_code: str
    machiaza_id: str | None = None
    lot: LotNumber = field(default_factory=LotNumber)

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[0-9]{6}", self.lg_code):
            raise ValueError(f"lg_code must be six digits, got {self.lg_code!r}.")
        if self.lg_code != self.with_check_digit(self.lg_code[:5]):
            raise ValueError(f"lg_code {self.lg_code!r} has an invalid check digit.")
        if self.machiaza_id is None:
            if self.lot.numbers:
                raise ValueError("Lot numbers require a machiaza_id.")
            return
        if not re.fullmatch(r"[0-9]{7}", self.machiaza_id):
            raise ValueError(f"machiaza_id must be seven digits, got {self.machiaza_id!r}.")
        if self.is_prefecture_code(self.lg_code):
            raise ValueError("A prefecture code cannot have a machiaza_id.")

    @classmethod
    def with_check_digit(cls, code_without_check_digit: str) -> str:
        """
        Append the check digit to a five-digit local government code.

        Parameters
        ----------
        code_without_check_digit : str
            First five digits of a local government code.

        Returns
        -------
        str
            Six-digit local government code.

        Raises
        ------
        ValueError
            If the input is not five digits.
        """
        if not re.fullmatch(r"[0-9]{5}", code_without_check_digit):
            raise ValueError(f"Expected five digits, got {code_without_check_digit!r}.")
        weighted_sum = sum(
            int(digit) * weight
            for digit, weight in zip(
                code_without_check_digit, cls._CHECK_DIGIT_WEIGHTS, strict=True
            )
        )
        return code_without_check_digit + str((11 - weighted_sum % 11) % 10)

    @classmethod
    def for_prefecture(cls, prefecture_code: str) -> Self:
        """
        Build the code of a prefecture.

        Parameters
        ----------
        prefecture_code : str
            Two-digit prefecture code, e.g. ``13`` for 東京都.

        Returns
        -------
        Self
            Prefecture-level address code such as ``130001``.
        """
        return cls(lg_code=cls.with_check_digit(prefecture_code + "000"))

    @staticmethod
    def is_prefecture_code(lg_code: str) -> bool:
        """
        Tell whether a local government code denotes a prefecture.

        Parameters
        ----------
        lg_code : str
            Six-digit local government code.

        Returns
        -------
        bool
            ``True`` when the third to fifth digits are ``000``.
        """
        return lg_code[2:5] == "000"

    @classmethod
    def parse(cls, text: str) -> Self:
        """
        Parse the string form of an address code.

        Parameters
        ----------
        text : str
            Code such as ``131067``, ``131067-0004000``, ``131016-0011001-2-3`` or
            ``113247-0001000-p124-1``. Full-width characters and dash variants such as
            ``‐`` and ``−`` are accepted.

        Returns
        -------
        Self
            Parsed address code.

        Raises
        ------
        ValueError
            If the text does not follow the address code format.
        """
        matched = cls._PATTERN.fullmatch(
            unicodedata.normalize("NFKC", text).translate(cls._DASHES).strip()
        )
        if matched is None:
            raise ValueError(f"Invalid address code: {text!r}.")
        numbers = [
            int(number)
            for number in matched.group("block", "residence", "branch")
            if number is not None
        ]
        system = (
            LotSystem.RESIDENCE_INDICATION
            if matched.group("parcel_marker") is None
            else LotSystem.LAND_PARCEL
        )
        return cls(
            lg_code=matched.group("lg_code"),
            machiaza_id=matched.group("machiaza_id"),
            lot=LotNumber.of(numbers, system),
        )

    @property
    def prefecture_code(self) -> str:
        """
        Two-digit prefecture code.

        Returns
        -------
        str
            First two digits of ``lg_code``.
        """
        return self.lg_code[:2]

    @property
    def level(self) -> AddressLevel:
        """
        Granularity of the code.

        Returns
        -------
        AddressLevel
            Level of the most specific component of the code.
        """
        if self.machiaza_id is None:
            if self.is_prefecture_code(self.lg_code):
                return AddressLevel.PREFECTURE
            return AddressLevel.MUNICIPALITY
        match len(self.lot.numbers):
            case 0:
                return AddressLevel.TOWN
            case 1:
                return AddressLevel.BLOCK
            case _:
                return AddressLevel.RESIDENCE

    @property
    def is_lot(self) -> bool:
        """
        Tell whether the code denotes a block or residence lot of a town.

        Returns
        -------
        bool
            ``True`` when the code has lot numbers, which require a ``machiaza_id``.
        """
        return bool(self.lot.numbers)

    @property
    def is_oaza(self) -> bool:
        """
        Tell whether the code denotes an oaza-level town.

        Returns
        -------
        bool
            ``True`` for a town without lot numbers whose chome part is ``000``.
        """
        return (
            self.machiaza_id is not None
            and not self.lot.numbers
            and self.machiaza_id.endswith(self._OAZA_CHOME_PART)
        )

    @property
    def parent(self) -> Self | None:
        """
        Code of the nearest enclosing area.

        A residence branch is enclosed by its residence, a residence by its block, and a
        block by its town. A land parcel and its branches are each enclosed by their
        town, because a branch is a separate parcel split off (分筆) from the original
        one. A chome or koaza is enclosed by its oaza (the town ID with the chome part
        ``000``) unless its ID has no oaza part (``0000``), an oaza or such a town by its
        municipality, a ward of a designated city by the city, and any other
        municipality by its prefecture. The enclosing oaza need not be registered.

        Returns
        -------
        Self | None
            Enclosing code, or ``None`` for a prefecture.
        """
        match self.level:
            case AddressLevel.PREFECTURE:
                return None
            case AddressLevel.MUNICIPALITY:
                city_code = DesignatedCity.find_code(self.lg_code)
                if city_code is not None:
                    return type(self)(lg_code=city_code)
                return self.for_prefecture(self.prefecture_code)
            case AddressLevel.RESIDENCE if not self.lot.is_land_parcel:
                return type(self)(
                    lg_code=self.lg_code,
                    machiaza_id=self.machiaza_id,
                    lot=self.lot.truncated(len(self.lot.numbers) - 1),
                )
            case AddressLevel.RESIDENCE | AddressLevel.BLOCK:
                return type(self)(lg_code=self.lg_code, machiaza_id=self.machiaza_id)
            case AddressLevel.TOWN:
                if (
                    self.machiaza_id is None
                    or self.is_oaza
                    or self.machiaza_id.startswith(self._ABSENT_OAZA_PART)
                ):
                    return type(self)(lg_code=self.lg_code)
                return type(self)(
                    lg_code=self.lg_code,
                    machiaza_id=self.machiaza_id[:4] + self._OAZA_CHOME_PART,
                )

    def lineage(self) -> list[Self]:
        """
        List this code followed by all its enclosing areas.

        Returns
        -------
        list[Self]
            Codes from this one up to its prefecture.
        """
        codes = [self]
        while (parent := codes[-1].parent) is not None:
            codes.append(parent)
        return codes

    def contains(self, other: Self) -> bool:
        """
        Tell whether another code lies within the area of this code.

        Parameters
        ----------
        other : Self
            Code to test.

        Returns
        -------
        bool
            ``True`` when ``other`` equals this code or one of its enclosing areas does,
            e.g. ``131067`` contains ``131067-0004001-2``.
        """
        return self in other.lineage()

    @override
    def __str__(self) -> str:
        components = [self.lg_code]
        if self.machiaza_id is not None:
            components.append(self.machiaza_id)
        lot_components = [str(number) for number in self.lot.numbers]
        if lot_components and self.lot.is_land_parcel:
            lot_components[0] = self._PARCEL_MARKER + lot_components[0]
        return "-".join([*components, *lot_components])
