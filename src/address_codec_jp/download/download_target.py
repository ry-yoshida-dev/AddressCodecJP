import re
from dataclasses import dataclass
from typing import ClassVar

from address_codec_jp.domain.address_code import AddressCode
from address_codec_jp.download.distribution_scope import DistributionScope
from address_codec_jp.download.registry_file import RegistryFile


@dataclass(frozen=True, slots=True)
class DownloadTarget:
    """
    One distributed file of a registry dataset.

    Parameters
    ----------
    registry_file : RegistryFile
        Dataset of the file.
    area_code : str | None
        Two-digit prefecture code for a per-prefecture dataset, six-digit local
        government code for a per-municipality dataset, or ``None`` for a nationwide one.

    Raises
    ------
    ValueError
        If ``area_code`` does not fit the distribution scope of the dataset.
    """

    _PREFECTURE_CODE: ClassVar[re.Pattern[str]] = re.compile(r"0[1-9]|[1-3][0-9]|4[0-7]")

    registry_file: RegistryFile
    area_code: str | None = None

    def __post_init__(self) -> None:
        match self.registry_file.scope, self.area_code:
            case DistributionScope.NATIONWIDE, None:
                pass
            case DistributionScope.PREFECTURE, str(code) if self._PREFECTURE_CODE.fullmatch(code):
                pass
            case DistributionScope.MUNICIPALITY, str(code):
                _ = AddressCode(lg_code=code)
                if AddressCode.is_prefecture_code(code):
                    raise ValueError(f"{code} is a prefecture code, not a municipality code.")
            case scope, code:
                raise ValueError(
                    f"{self.registry_file.name} is distributed {scope.name.lower()}, "
                    + f"which does not take the area code {code!r}."
                )

    @property
    def file_name(self) -> str:
        """
        Name of the distributed file.

        Returns
        -------
        str
            File name such as ``mt_town_pos_pref13.csv.zip``.
        """
        prefix = self.registry_file.value
        match self.registry_file.scope:
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
        prefix = self.registry_file.value
        match self.registry_file.scope:
            case DistributionScope.NATIONWIDE:
                return f"{prefix}/{self.file_name}"
            case DistributionScope.PREFECTURE:
                return f"{prefix}/pref/{self.file_name}"
            case DistributionScope.MUNICIPALITY:
                return f"{prefix}/city/{self.file_name}"
