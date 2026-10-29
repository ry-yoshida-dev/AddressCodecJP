from dataclasses import dataclass

from address_codec_jp.frontends.api.data_source import DataSource


@dataclass(frozen=True, slots=True)
class DataAttribution:
    """
    Dataset to credit for a response, with the municipality it was used for.

    Parameters
    ----------
    source : DataSource
        Dataset used.
    lg_code : str
        Municipality whose data was used, or an empty string for datasets credited as a
        whole.
    """

    source: DataSource
    lg_code: str = ""

    @property
    def sort_key(self) -> tuple[int, str]:
        """
        Order of the credit among others.

        Returns
        -------
        tuple[int, str]
            Definition order of ``source``, then ``lg_code``.
        """
        return list(DataSource).index(self.source), self.lg_code
