from collections.abc import Iterable, Mapping
from datetime import date
from typing import ClassVar, assert_never

from address_codec_jp.address_codec import AddressCodec
from address_codec_jp.api.data_attribution import DataAttribution
from address_codec_jp.api.data_source import DataSource
from address_codec_jp.domain.address_code import AddressCode
from address_codec_jp.formatting.address_format import AddressFormat


class CreditWriter:
    """
    Writer of the source credits that the terms of use of the datasets require.

    The Public Data License 1.0, the e-Stat terms of use, and the terms of use of the
    registry office map data all require the source, the fact that the data was
    processed, and who processed it. Credits follow the examples of those terms, in
    Japanese; registry map credits name the municipality and the date its maps were
    obtained.

    Parameters
    ----------
    codec : AddressCodec
        Codec that renders municipality names.
    publisher : str
        Organization that processes and serves the data.
    registry_map_dates : Mapping[str, date]
        Date the registry maps of each municipality were obtained.
    """

    ADDRESS_BASE_REGISTRY_URL: ClassVar[str] = (
        "https://www.digital.go.jp/policies/base_registry_address"
    )
    PUBLIC_DATA_LICENSE_URL: ClassVar[str] = (
        "https://www.digital.go.jp/resources/open_data/public_data_license_v1.0"
    )
    E_STAT_URL: ClassVar[str] = "https://www.e-stat.go.jp/"
    REGISTRY_MAP_SEARCH_URL: ClassVar[str] = "https://www.geospatial.jp/ckan/dataset?q={code}"
    _NAME_FORMAT: ClassVar[AddressFormat] = AddressFormat(is_prefecture_included=False)

    def __init__(
        self, codec: AddressCodec, publisher: str, registry_map_dates: Mapping[str, date]
    ) -> None:
        self._codec: AddressCodec = codec
        self._publisher: str = publisher
        self._registry_map_dates: Mapping[str, date] = registry_map_dates

    def write(self, attributions: Iterable[DataAttribution]) -> list[str]:
        """
        Write the credits of datasets.

        Parameters
        ----------
        attributions : Iterable[DataAttribution]
            Datasets used, possibly repeated.

        Returns
        -------
        list[str]
            One credit per distinct attribution, ordered by dataset and municipality.
        """
        return [
            self._credit(attribution)
            for attribution in sorted(
                set(attributions), key=lambda attribution: attribution.sort_key
            )
        ]

    def _credit(self, attribution: DataAttribution) -> str:
        processed = f"を加工して{self._publisher}が作成"
        registry_page = f"（デジタル庁）（{self.ADDRESS_BASE_REGISTRY_URL}）"
        match attribution.source:
            case DataSource.ADDRESS_BASE_REGISTRY:
                license_text = f"（公共データ利用規約 第1.0版 {self.PUBLIC_DATA_LICENSE_URL}）"
                return (
                    f"出典：「アドレス・ベース・レジストリ」{registry_page}"
                    + f"{license_text}{processed}"
                )
            case DataSource.PARCEL_MASTER:
                return (
                    f"出典：{self._registry_map(attribution.lg_code)}を参照元とする"
                    + f"「アドレス・ベース・レジストリ 地番マスター」{registry_page}{processed}"
                )
            case DataSource.CENSUS_BOUNDARY:
                return (
                    f"出典：政府統計の総合窓口(e-Stat)（{self.E_STAT_URL}）"
                    + "「令和2年国勢調査 町丁・字等境界データ」（総務省統計局）"
                    + processed
                )
            case DataSource.REGISTRY_MAP:
                obtained = self._registry_map_dates.get(attribution.lg_code)
                obtained_text = (
                    ""
                    if obtained is None
                    else f"（{obtained.year}年{obtained.month}月{obtained.day}日に利用）"
                )
                return f"出典：{self._registry_map(attribution.lg_code)}{obtained_text}{processed}"
            case _:
                assert_never(attribution.source)

    def _registry_map(self, lg_code: str) -> str:
        url = self.REGISTRY_MAP_SEARCH_URL.format(code=lg_code[:5])
        return f"「登記所備付地図データ {self._municipality_name(lg_code)}」（法務省）（{url}）"

    def _municipality_name(self, lg_code: str) -> str:
        return self._codec.decode(AddressCode(lg_code=lg_code), self._NAME_FORMAT)
