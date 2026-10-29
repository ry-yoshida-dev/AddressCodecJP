import json
import re
import zipfile
from pathlib import Path
from typing import ClassVar, cast

from address_codec_jp.address import AddressCode
from address_codec_jp.datasets.download.file_fetcher import FileFetcher
from address_codec_jp.errors import RegistryDownloadError


class BoundaryDownloader:
    """
    Downloader of the area shapes of a municipality.

    Town boundaries come from the 2020 census on e-Stat, as a shapefile of latitude and
    longitude on JGD2011. Land parcel maps of the registry offices are looked up in the
    catalog of the G-Spatial Information Center, which lists one archive per registry
    office and year; the latest year of each office is downloaded. The catalog is read
    page by page with the ``start`` parameter until its reported ``count`` is reached.

    Parameters
    ----------
    census_url_template : str
        URL of the boundary archive of a municipality, with ``{code}`` for its
        five-digit code.
    catalog_url_template : str
        URL of the CKAN ``package_search`` for the maps of a municipality, with ``{code}``
        for its five-digit code.
    timeout_seconds : float
        Timeout of each network operation.

    Raises
    ------
    ValueError
        If ``timeout_seconds`` is not positive.
    """

    DEFAULT_CENSUS_URL_TEMPLATE: ClassVar[str] = (
        "https://www.e-stat.go.jp/gis/statmap-search/data?dlserveyId=A002005212020"
        + "&code={code}&coordSys=1&format=shape&downloadType=5&datum=2011"
    )
    DEFAULT_CATALOG_URL_TEMPLATE: ClassVar[str] = (
        "https://www.geospatial.jp/ckan/api/3/action/package_search"
        + "?q={code}&fq=organization:moj-*&rows=100"
    )

    def __init__(
        self,
        census_url_template: str = DEFAULT_CENSUS_URL_TEMPLATE,
        catalog_url_template: str = DEFAULT_CATALOG_URL_TEMPLATE,
        timeout_seconds: float = 120.0,
    ) -> None:
        self._census_url_template: str = census_url_template
        self._catalog_url_template: str = catalog_url_template
        self._fetcher: FileFetcher = FileFetcher(timeout_seconds)

    def download_census_boundary(self, lg_code: str, directory: Path) -> Path | None:
        """
        Download the town boundaries of a municipality.

        Parameters
        ----------
        lg_code : str
            Six-digit local government code of the municipality.
        directory : Path
            Directory that receives ``census_boundary_{lg_code}.zip``.

        Returns
        -------
        Path | None
            Path of the archive, or ``None`` when e-Stat has no boundaries for the code.

        Raises
        ------
        ValueError
            If the code is malformed.
        RegistryDownloadError
            If the archive cannot be downloaded.
        """
        code = self._five_digit_code(lg_code)
        destination = directory / f"census_boundary_{lg_code}.zip"
        path = self._fetcher.fetch_if_present(
            self._census_url_template.format(code=code), destination
        )
        if path is None:
            return None
        if self._is_empty_archive(path):
            path.unlink()
            return None
        return path

    def list_registry_map_urls(self, lg_code: str) -> list[str]:
        """
        Find the latest land parcel map archive of each registry office of a municipality.

        Parameters
        ----------
        lg_code : str
            Six-digit local government code of the municipality.

        Returns
        -------
        list[str]
            Archive URLs ordered by file name; empty when the catalog lists none.

        Raises
        ------
        ValueError
            If the code is malformed.
        RegistryDownloadError
            If the catalog cannot be searched or its response is not a CKAN search result.
        """
        code = self._five_digit_code(lg_code)
        file_pattern = re.compile(rf"(?:^|/)({code}-(\d{{4}})-(\d{{4}})\.zip)$")
        latest: dict[str, tuple[str, str]] = {}
        for url in self._list_catalog_urls(self._catalog_url_template.format(code=code)):
            match_result = file_pattern.search(url)
            if match_result is None:
                continue
            office, year = match_result.group(2), match_result.group(3)
            if office not in latest or year > latest[office][0]:
                latest[office] = (year, url)
        return [latest[office][1] for office in sorted(latest)]

    def download_registry_maps(self, lg_code: str, directory: Path) -> list[Path]:
        """
        Download the latest land parcel maps of a municipality.

        Parameters
        ----------
        lg_code : str
            Six-digit local government code of the municipality.
        directory : Path
            Directory that receives the archives under their published names.

        Returns
        -------
        list[Path]
            Downloaded archives; empty when the catalog lists none.

        Raises
        ------
        ValueError
            If the code is malformed.
        RegistryDownloadError
            If the catalog cannot be searched or an archive cannot be downloaded.
        """
        return [
            self._fetcher.fetch(url, directory / url.rsplit("/", 1)[-1])
            for url in self.list_registry_map_urls(lg_code)
        ]

    def _list_catalog_urls(self, search_url: str) -> list[str]:
        urls: list[str] = []
        package_count = 0
        while True:
            page_url = search_url if package_count == 0 else f"{search_url}&start={package_count}"
            result = self._read_search_result(page_url)
            packages = self._as_list(result.get("results"), page_url)
            for package in packages:
                resources = self._as_list(
                    self._as_dict(package, page_url).get("resources"), page_url
                )
                for resource in resources:
                    url = self._as_dict(resource, page_url).get("url")
                    if isinstance(url, str):
                        urls.append(url)
            package_count += len(packages)
            total_count = result.get("count")
            if not packages or not isinstance(total_count, int) or package_count >= total_count:
                return urls

    def _read_search_result(self, url: str) -> dict[str, object]:
        try:
            response = cast(object, json.loads(self._fetcher.read(url)))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise RegistryDownloadError(
                f"Catalog response of {url} is not JSON: {error}"
            ) from error
        return self._as_dict(self._as_dict(response, url).get("result"), url)

    def _as_dict(self, value: object, url: str) -> dict[str, object]:
        if not isinstance(value, dict):
            raise RegistryDownloadError(f"Unexpected catalog response from {url}.")
        return {str(key): item for key, item in cast(dict[object, object], value).items()}

    def _as_list(self, value: object, url: str) -> list[object]:
        if not isinstance(value, list):
            raise RegistryDownloadError(f"Unexpected catalog response from {url}.")
        return list(cast(list[object], value))

    def _is_empty_archive(self, path: Path) -> bool:
        if not zipfile.is_zipfile(path):
            return True
        with zipfile.ZipFile(path) as archive:
            return not archive.namelist()

    def _five_digit_code(self, lg_code: str) -> str:
        code = AddressCode(lg_code=lg_code)
        if AddressCode.is_prefecture_code(code.lg_code):
            raise ValueError(f"{lg_code} is a prefecture code, not a municipality code.")
        return code.lg_code[:5]
