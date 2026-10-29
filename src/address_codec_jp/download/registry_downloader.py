from collections.abc import Sequence
from pathlib import Path
from typing import ClassVar

from address_codec_jp.download.distributed_file import DistributedFile
from address_codec_jp.download.file_fetcher import FileFetcher
from address_codec_jp.registry.abr_dataset import AbrDataset
from address_codec_jp.registry.distribution_scope import DistributionScope


class RegistryDownloader:
    """
    Downloader of Address Base Registry files from the registry download site.

    A file is written under a temporary name and renamed when complete, so that an
    interrupted or truncated download never leaves a file under the final name.

    Parameters
    ----------
    base_url : str
        URL of the download site. Any URL scheme that ``urllib`` opens is accepted,
        including ``file://`` for a local mirror.
    timeout_seconds : float
        Timeout of each network operation.

    Raises
    ------
    ValueError
        If ``timeout_seconds`` is not positive.

    Examples
    --------
    >>> downloader = RegistryDownloader()
    >>> for distributed_file in downloader.plan(prefecture_codes=["13"]):  # doctest: +SKIP
    ...     downloader.download(distributed_file, Path("data"))
    """

    DEFAULT_BASE_URL: ClassVar[str] = "https://data.address-br.digital.go.jp"

    def __init__(self, base_url: str = DEFAULT_BASE_URL, timeout_seconds: float = 60.0) -> None:
        self._base_url: str = base_url.rstrip("/")
        self._fetcher: FileFetcher = FileFetcher(timeout_seconds)

    def plan(
        self, prefecture_codes: Sequence[str] = (), municipality_codes: Sequence[str] = ()
    ) -> list[DistributedFile]:
        """
        List the files needed to encode, decode, and locate addresses of some areas.

        Parameters
        ----------
        prefecture_codes : Sequence[str]
            Two-digit codes of the prefectures whose town, block, and residence points
            are wanted.
        municipality_codes : Sequence[str]
            Six-digit local government codes of the municipalities whose land parcels
            are wanted.

        Returns
        -------
        list[DistributedFile]
            The nationwide town master and prefecture and municipality points first,
            then the files of each area, in the order they should be imported.

        Raises
        ------
        ValueError
            If a code is malformed.
        """
        return [
            *(DistributedFile(dataset) for dataset in self._datasets(DistributionScope.NATIONWIDE)),
            *(
                DistributedFile(dataset, prefecture_code)
                for prefecture_code in dict.fromkeys(prefecture_codes)
                for dataset in self._datasets(DistributionScope.PREFECTURE)
            ),
            *(
                DistributedFile(dataset, municipality_code)
                for municipality_code in dict.fromkeys(municipality_codes)
                for dataset in self._datasets(DistributionScope.MUNICIPALITY)
            ),
        ]

    def plan_lots(self, municipality_codes: Sequence[str]) -> list[DistributedFile]:
        """
        List the files of the blocks, residences, and land parcels of municipalities.

        Parameters
        ----------
        municipality_codes : Sequence[str]
            Six-digit local government codes of the municipalities.

        Returns
        -------
        list[DistributedFile]
            Block and residence indication files and land parcel files of each
            municipality, in the order they should be imported.

        Raises
        ------
        ValueError
            If a code is malformed.
        """
        return [
            DistributedFile(dataset, municipality_code)
            for municipality_code in dict.fromkeys(municipality_codes)
            for dataset in AbrDataset
            if dataset.scope is not DistributionScope.NATIONWIDE
            and DistributionScope.MUNICIPALITY in dataset.scopes
        ]

    def url_of(self, distributed_file: DistributedFile) -> str:
        """
        Build the URL of a file on the download site.

        Parameters
        ----------
        distributed_file : DistributedFile
            File to locate.

        Returns
        -------
        str
            Full URL of the file.
        """
        return f"{self._base_url}/{distributed_file.url_path}"

    def download(
        self, distributed_file: DistributedFile, directory: Path, *, is_existing_kept: bool = False
    ) -> Path:
        """
        Download one file into a directory.

        Parameters
        ----------
        distributed_file : DistributedFile
            File to download.
        directory : Path
            Directory that receives the file under its distributed name. It is created
            if needed.
        is_existing_kept : bool
            Whether a file already present under the name is kept instead of being
            downloaded again.

        Returns
        -------
        Path
            Path of the downloaded file.

        Raises
        ------
        RegistryDownloadError
            If the file cannot be fetched or written, or fewer bytes arrive than the
            server announced. Nothing is left under the final name then.
        """
        destination = directory / distributed_file.file_name
        if is_existing_kept and destination.is_file():
            return destination
        return self._fetcher.fetch(self.url_of(distributed_file), destination)

    def download_if_distributed(
        self, distributed_file: DistributedFile, directory: Path
    ) -> Path | None:
        """
        Download one file into a directory unless the site does not distribute it.

        The site has no file for some areas, such as the land parcels of the
        municipalities of the Northern Territories or of a designated city as a whole.

        Parameters
        ----------
        distributed_file : DistributedFile
            File to download.
        directory : Path
            Directory that receives the file under its distributed name. It is created
            if needed.

        Returns
        -------
        Path | None
            Path of the downloaded file, or ``None`` when the site has no such file.

        Raises
        ------
        RegistryDownloadError
            If the file exists but cannot be fetched or written, or fewer bytes arrive
            than the server announced. Nothing is left under the final name then.
        """
        return self._fetcher.fetch_if_present(
            self.url_of(distributed_file), directory / distributed_file.file_name
        )

    def _datasets(self, scope: DistributionScope) -> list[AbrDataset]:
        return [dataset for dataset in AbrDataset if dataset.scope is scope]
