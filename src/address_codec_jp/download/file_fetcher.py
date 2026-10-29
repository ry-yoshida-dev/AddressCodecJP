import http
import http.client
import shutil
import urllib.error
import urllib.request
import urllib.response
from pathlib import Path
from typing import ClassVar, cast

from address_codec_jp.errors.registry_download_error import RegistryDownloadError


class FileFetcher:
    """
    Downloader of one URL into a file, written atomically.

    A file is written under a temporary name and renamed when complete, so that an
    interrupted or truncated download never leaves a file under the final name.

    Parameters
    ----------
    timeout_seconds : float
        Timeout of each network operation.

    Raises
    ------
    ValueError
        If ``timeout_seconds`` is not positive.
    """

    _USER_AGENT: ClassVar[str] = "address-codec-jp"
    _PARTIAL_SUFFIX: ClassVar[str] = ".part"

    def __init__(self, timeout_seconds: float = 60.0) -> None:
        if not timeout_seconds > 0:
            raise ValueError(f"timeout_seconds must be positive, got {timeout_seconds}.")
        self._timeout_seconds: float = timeout_seconds

    def fetch(self, url: str, destination: Path) -> Path:
        """
        Download a URL.

        Parameters
        ----------
        url : str
            URL of any scheme that ``urllib`` opens.
        destination : Path
            File to write. Its directory is created if needed.

        Returns
        -------
        Path
            ``destination``.

        Raises
        ------
        RegistryDownloadError
            If the URL cannot be fetched or written, or fewer bytes arrive than the
            server announced. Nothing is left under ``destination`` then.
        """
        fetched = self._fetch(url, destination, is_missing_allowed=False)
        if fetched is None:
            raise RuntimeError(f"{url} was neither downloaded nor missing.")
        return fetched

    def fetch_if_present(self, url: str, destination: Path) -> Path | None:
        """
        Download a URL unless the server has nothing there.

        Parameters
        ----------
        url : str
            URL of any scheme that ``urllib`` opens.
        destination : Path
            File to write. Its directory is created if needed.

        Returns
        -------
        Path | None
            ``destination``, or ``None`` for an HTTP 404 response or a missing local file.

        Raises
        ------
        RegistryDownloadError
            If the URL exists but cannot be fetched or written, or fewer bytes arrive
            than the server announced. Nothing is left under ``destination`` then.
        """
        return self._fetch(url, destination, is_missing_allowed=True)

    def read(self, url: str) -> bytes:
        """
        Download a URL into memory.

        Parameters
        ----------
        url : str
            URL of any scheme that ``urllib`` opens.

        Returns
        -------
        bytes
            Body of the response.

        Raises
        ------
        RegistryDownloadError
            If the URL cannot be fetched.
        """
        request = urllib.request.Request(url, headers={"User-Agent": self._USER_AGENT})
        try:
            opened = cast(object, urllib.request.urlopen(request, timeout=self._timeout_seconds))
            if not isinstance(opened, http.client.HTTPResponse | urllib.response.addinfourl):
                raise RuntimeError(f"Unexpected response type {type(opened).__name__}.")
            with opened as response:
                return response.read()
        except (OSError, http.client.HTTPException) as error:
            raise RegistryDownloadError(f"Could not download {url}: {error}") from error

    def _fetch(self, url: str, destination: Path, *, is_missing_allowed: bool) -> Path | None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        partial = destination.with_name(destination.name + self._PARTIAL_SUFFIX)
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
