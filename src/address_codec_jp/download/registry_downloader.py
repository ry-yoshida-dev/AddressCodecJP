import http
import http.client
import shutil
import urllib.error
import urllib.request
import urllib.response
from collections.abc import Sequence
from pathlib import Path
from typing import ClassVar, cast

from address_codec_jp.download.distributed_file import DistributedFile
from address_codec_jp.errors.registry_download_error import RegistryDownloadError
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
    _USER_AGENT: ClassVar[str] = "address-codec-jp"
    _PARTIAL_SUFFIX: ClassVar[str] = ".part"

    def __init__(self, base_url: str = DEFAULT_BASE_URL, timeout_seconds: float = 60.0) -> None:
        if not timeout_seconds > 0:
            raise ValueError(f"timeout_seconds must be positive, got {timeout_seconds}.")
        self._base_url: str = base_url.rstrip("/")
        self._timeout_seconds: float = timeout_seconds

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
        downloaded = self._fetch(distributed_file, destination, is_missing_allowed=False)
        if downloaded is None:
            raise RuntimeError(f"{distributed_file.file_name} was neither downloaded nor missing.")
        return downloaded

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
        return self._fetch(
            distributed_file, directory / distributed_file.file_name, is_missing_allowed=True
        )

    def _fetch(
        self, distributed_file: DistributedFile, destination: Path, *, is_missing_allowed: bool
    ) -> Path | None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        partial = destination.with_name(destination.name + self._PARTIAL_SUFFIX)
        url = self.url_of(distributed_file)
        request = urllib.request.Request(url, headers={"User-Agent": self._USER_AGENT})
        is_complete = False
        try:
            self._copy(request, partial)
            is_complete = True
        except RegistryDownloadError:
            raise
        except (OSError, http.client.HTTPException) as error:
            if is_missing_allowed and self._is_missing(error):
                return None
            raise RegistryDownloadError(f"Could not download {url}: {error}") from error
        finally:
            if not is_complete:
                partial.unlink(missing_ok=True)
        return partial.replace(destination)

    def _is_missing(self, error: OSError | http.client.HTTPException) -> bool:
        match error:
            case urllib.error.HTTPError(code=http.HTTPStatus.NOT_FOUND):
                return True
            case urllib.error.URLError(reason=FileNotFoundError()):
                return True
            case _:
                return False

    def _datasets(self, scope: DistributionScope) -> list[AbrDataset]:
        return [dataset for dataset in AbrDataset if dataset.scope is scope]

    def _copy(self, request: urllib.request.Request, destination: Path) -> None:
        opened = cast(object, urllib.request.urlopen(request, timeout=self._timeout_seconds))
        if not isinstance(opened, http.client.HTTPResponse | urllib.response.addinfourl):
            raise RuntimeError(f"Unexpected response type {type(opened).__name__}.")
        with opened as response, destination.open("wb") as stream:
            shutil.copyfileobj(response, stream)
            announced_length = response.headers.get("Content-Length")
        received_length = destination.stat().st_size
        if announced_length is not None and int(announced_length) != received_length:
            raise RegistryDownloadError(
                f"Received {received_length} of {announced_length} bytes from "
                + f"{request.full_url}."
            )
