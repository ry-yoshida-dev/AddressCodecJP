import http.client
import shutil
import urllib.error
import urllib.request
import urllib.response
from collections.abc import Sequence
from pathlib import Path
from typing import ClassVar, cast

from address_codec_jp.download.download_target import DownloadTarget
from address_codec_jp.download.registry_file import RegistryFile
from address_codec_jp.errors.registry_download_error import RegistryDownloadError


class RegistryDownloader:
    """
    Downloader of Address Base Registry files from the registry download site.

    A file is written under a temporary name and renamed when complete, so that an
    interrupted download never leaves a truncated file under the final name.

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
    >>> for target in downloader.plan(prefecture_codes=["13"]):  # doctest: +SKIP
    ...     downloader.download(target, Path("data"))
    """

    DEFAULT_BASE_URL: ClassVar[str] = "https://data.address-br.digital.go.jp"
    _USER_AGENT: ClassVar[str] = "address-codec-jp"
    _PARTIAL_SUFFIX: ClassVar[str] = ".part"
    _NATIONWIDE_FILES: ClassVar[tuple[RegistryFile, ...]] = (
        RegistryFile.TOWN,
        RegistryFile.PREFECTURE_POSITION,
        RegistryFile.MUNICIPALITY_POSITION,
    )
    _PREFECTURE_FILES: ClassVar[tuple[RegistryFile, ...]] = (
        RegistryFile.TOWN_POSITION,
        RegistryFile.BLOCK,
        RegistryFile.BLOCK_POSITION,
        RegistryFile.RESIDENCE,
        RegistryFile.RESIDENCE_POSITION,
    )
    _MUNICIPALITY_FILES: ClassVar[tuple[RegistryFile, ...]] = (
        RegistryFile.PARCEL,
        RegistryFile.PARCEL_POSITION,
    )

    def __init__(self, base_url: str = DEFAULT_BASE_URL, timeout_seconds: float = 60.0) -> None:
        if not timeout_seconds > 0:
            raise ValueError(f"timeout_seconds must be positive, got {timeout_seconds}.")
        self._base_url: str = base_url.rstrip("/")
        self._timeout_seconds: float = timeout_seconds

    def plan(
        self, prefecture_codes: Sequence[str] = (), municipality_codes: Sequence[str] = ()
    ) -> list[DownloadTarget]:
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
        list[DownloadTarget]
            The nationwide town master and prefecture and municipality points first,
            then the files of each area, in the order they should be imported.

        Raises
        ------
        ValueError
            If a code is malformed.
        """
        return [
            *(DownloadTarget(registry_file) for registry_file in self._NATIONWIDE_FILES),
            *(
                DownloadTarget(registry_file, prefecture_code)
                for prefecture_code in dict.fromkeys(prefecture_codes)
                for registry_file in self._PREFECTURE_FILES
            ),
            *(
                DownloadTarget(registry_file, municipality_code)
                for municipality_code in dict.fromkeys(municipality_codes)
                for registry_file in self._MUNICIPALITY_FILES
            ),
        ]

    def url_of(self, target: DownloadTarget) -> str:
        """
        Build the URL of a file on the download site.

        Parameters
        ----------
        target : DownloadTarget
            File to locate.

        Returns
        -------
        str
            Full URL of the file.
        """
        return f"{self._base_url}/{target.url_path}"

    def download(
        self, target: DownloadTarget, directory: Path, *, is_existing_kept: bool = False
    ) -> Path:
        """
        Download one file into a directory.

        Parameters
        ----------
        target : DownloadTarget
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
            If the file cannot be fetched. Nothing is left under the final name then.
        """
        destination = directory / target.file_name
        if is_existing_kept and destination.is_file():
            return destination
        directory.mkdir(parents=True, exist_ok=True)
        partial = destination.with_name(destination.name + self._PARTIAL_SUFFIX)
        url = self.url_of(target)
        request = urllib.request.Request(url, headers={"User-Agent": self._USER_AGENT})
        try:
            self._copy(request, partial)
        except (urllib.error.URLError, TimeoutError) as error:
            partial.unlink(missing_ok=True)
            raise RegistryDownloadError(f"Could not download {url}: {error}") from error
        return partial.replace(destination)

    def _copy(self, request: urllib.request.Request, destination: Path) -> None:
        opened = cast(object, urllib.request.urlopen(request, timeout=self._timeout_seconds))
        if not isinstance(opened, http.client.HTTPResponse | urllib.response.addinfourl):
            raise RuntimeError(f"Unexpected response type {type(opened).__name__}.")
        with opened as response, destination.open("wb") as stream:
            shutil.copyfileobj(response, stream)
