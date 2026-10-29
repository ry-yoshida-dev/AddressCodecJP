import re
from dataclasses import dataclass
from typing import Self

from address_codec_jp.domain.address_code import AddressCode
from address_codec_jp.domain.prefecture import Prefecture
from address_codec_jp.registry.abr_dataset import AbrDataset
from address_codec_jp.registry.distribution_scope import DistributionScope

_FILE_NAME_PATTERN: re.Pattern[str] = re.compile(
    r"(?P<prefix>[a-z_]+?)_(?:all|pref(?P<prefecture>\d{2})|city(?P<municipality>\d{6}))\.csv\.zip"
)


@dataclass(frozen=True, slots=True)
class DistributedFile:
    """
    One distributed file of a registry dataset.

    Parameters
    ----------
    dataset : AbrDataset
        Dataset of the file.
    area_code : str | None
        Two-digit prefecture code for a file of a prefecture, six-digit local government
        code for a file of a municipality, or ``None`` for a nationwide file.

    Raises
    ------
    ValueError
        If ``area_code`` is malformed, or the dataset is not distributed per its area.
    """

    dataset: AbrDataset
    area_code: str | None = None

    def __post_init__(self) -> None:
        if self.scope not in self.dataset.scopes:
            raise ValueError(
                f"{self.dataset.name} is not distributed {self.scope.name.lower()}, "
                + f"which the area code {self.area_code!r} asks for."
            )

    @classmethod
    def from_file_name(cls, file_name: str) -> Self | None:
        """
        Identify a distributed file by its name.

        Parameters
        ----------
        file_name : str
            Name such as ``mt_town_pos_pref13.csv.zip``.

        Returns
        -------
        Self | None
            File of that name, or ``None`` for a name the registry does not distribute.
        """
        match_result = _FILE_NAME_PATTERN.fullmatch(file_name)
        if match_result is None:
            return None
        datasets = {dataset.value: dataset for dataset in AbrDataset}
        dataset = datasets.get(match_result.group("prefix"))
        if dataset is None:
            return None
        prefecture_code = match_result.group("prefecture")
        municipality_code = match_result.group("municipality")
        if prefecture_code is not None:
            is_valid = (
                Prefecture.is_code(prefecture_code)
                and DistributionScope.PREFECTURE in dataset.scopes
            )
            return cls(dataset, prefecture_code) if is_valid else None
        if municipality_code is not None:
            is_valid = (
                DistributionScope.MUNICIPALITY in dataset.scopes
                and AddressCode.with_check_digit(municipality_code[:5]) == municipality_code
                and not AddressCode.is_prefecture_code(municipality_code)
            )
            return cls(dataset, municipality_code) if is_valid else None
        return cls(dataset) if DistributionScope.NATIONWIDE in dataset.scopes else None

    @property
    def scope(self) -> DistributionScope:
        """
        Area unit of the file.

        Returns
        -------
        DistributionScope
            Nationwide without an area code, per prefecture for a prefecture code, and
            per municipality for a local government code.

        Raises
        ------
        ValueError
            If the area code is neither a prefecture code nor a municipality code.
        """
        match self.area_code:
            case None:
                return DistributionScope.NATIONWIDE
            case str(code) if Prefecture.is_code(code):
                return DistributionScope.PREFECTURE
            case str(code):
                _ = AddressCode(lg_code=code)
                if AddressCode.is_prefecture_code(code):
                    raise ValueError(f"{code} is a prefecture code, not a municipality code.")
                return DistributionScope.MUNICIPALITY

    @property
    def file_name(self) -> str:
        """
        Name of the distributed file.

        Returns
        -------
        str
            File name such as ``mt_town_pos_pref13.csv.zip``.
        """
        prefix = self.dataset.value
        match self.scope:
            case DistributionScope.NATIONWIDE:
                return f"{prefix}_all.csv.zip"
            case DistributionScope.PREFECTURE:
                return f"{prefix}_pref{self.area_code}.csv.zip"
            case DistributionScope.MUNICIPALITY:
                return f"{prefix}_city{self.area_code}.csv.zip"

    @property
    def url_path(self) -> str:
        """
        Path of the file below the base URL of the download site.

        Returns
        -------
        str
            Path such as ``mt_town_pos/pref/mt_town_pos_pref13.csv.zip``.
        """
        prefix = self.dataset.value
        match self.scope:
            case DistributionScope.NATIONWIDE:
                return f"{prefix}/{self.file_name}"
            case DistributionScope.PREFECTURE:
                return f"{prefix}/pref/{self.file_name}"
            case DistributionScope.MUNICIPALITY:
                return f"{prefix}/city/{self.file_name}"
