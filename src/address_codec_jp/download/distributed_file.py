from dataclasses import dataclass

from address_codec_jp.domain.address_code import AddressCode
from address_codec_jp.domain.prefecture import Prefecture
from address_codec_jp.registry.abr_dataset import AbrDataset
from address_codec_jp.registry.distribution_scope import DistributionScope


@dataclass(frozen=True, slots=True)
class DistributedFile:
    """
    One distributed file of a registry dataset.

    Parameters
    ----------
    dataset : AbrDataset
        Dataset of the file.
    area_code : str | None
        Two-digit prefecture code for a per-prefecture dataset, six-digit local
        government code for a per-municipality dataset, or ``None`` for a nationwide one.

    Raises
    ------
    ValueError
        If ``area_code`` does not fit the distribution scope of the dataset.
    """

    dataset: AbrDataset
    area_code: str | None = None

    def __post_init__(self) -> None:
        match self.dataset.scope, self.area_code:
            case DistributionScope.NATIONWIDE, None:
                pass
            case DistributionScope.PREFECTURE, str(code) if Prefecture.is_code(code):
                pass
            case DistributionScope.MUNICIPALITY, str(code):
                _ = AddressCode(lg_code=code)
                if AddressCode.is_prefecture_code(code):
                    raise ValueError(f"{code} is a prefecture code, not a municipality code.")
            case scope, code:
                raise ValueError(
                    f"{self.dataset.name} is distributed {scope.name.lower()}, "
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
        prefix = self.dataset.value
        match self.dataset.scope:
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
        match self.dataset.scope:
            case DistributionScope.NATIONWIDE:
                return f"{prefix}/{self.file_name}"
            case DistributionScope.PREFECTURE:
                return f"{prefix}/pref/{self.file_name}"
            case DistributionScope.MUNICIPALITY:
                return f"{prefix}/city/{self.file_name}"
