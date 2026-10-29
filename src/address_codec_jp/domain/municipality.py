from dataclasses import dataclass

from address_codec_jp.domain.prefecture import Prefecture


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
    """

    lg_code: str
    prefecture_name: str
    county_name: str
    city_name: str
    ward_name: str

    @property
    def prefecture(self) -> Prefecture:
        """
        Prefecture that contains this municipality.

        Returns
        -------
        Prefecture
            Prefecture built from the first two digits of ``lg_code``.
        """
        return Prefecture(code=self.lg_code[:2], name=self.prefecture_name)
