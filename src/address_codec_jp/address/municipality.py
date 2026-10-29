from dataclasses import dataclass

from address_codec_jp.address.code import AddressCode
from address_codec_jp.address.prefecture import Prefecture


@dataclass(frozen=True, slots=True)
class Municipality:
    """
    Municipality identified by a local government code.

    Parameters
    ----------
    lg_code : str
        Six-digit local government code (全国地方公共団体コード).
    prefecture_name : str
        Prefecture name, e.g. ``東京都``.
    county_name : str
        County name, or an empty string when the municipality is not in a county.
    city_name : str
        City, town, village, or special ward name.
    ward_name : str
        Ward name of a designated city, or an empty string.
    prefecture_kana : str
        Katakana reading of ``prefecture_name``.
    county_kana : str
        Katakana reading of ``county_name``.
    city_kana : str
        Katakana reading of ``city_name``.
    ward_kana : str
        Katakana reading of ``ward_name``.

    Readings are empty strings when the name is empty or the registry has no reading.

    Raises
    ------
    ValueError
        If ``lg_code`` is malformed, denotes a prefecture, or does not start with a
        prefecture code.
    """

    lg_code: str
    prefecture_name: str
    county_name: str
    city_name: str
    ward_name: str
    prefecture_kana: str
    county_kana: str
    city_kana: str
    ward_kana: str

    def __post_init__(self) -> None:
        _ = AddressCode(lg_code=self.lg_code)
        if AddressCode.is_prefecture_code(self.lg_code):
            raise ValueError(f"{self.lg_code} is a prefecture code, not a municipality code.")
        _ = self.prefecture

    @property
    def prefecture(self) -> Prefecture:
        """
        Prefecture that contains this municipality.

        Returns
        -------
        Prefecture
            Prefecture built from the first two digits of ``lg_code``.
        """
        return Prefecture(
            code=self.lg_code[:2], name=self.prefecture_name, kana=self.prefecture_kana
        )
