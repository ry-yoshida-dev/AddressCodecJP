from typing import ClassVar

from pydantic import BaseModel, ConfigDict


class ValidationIssue(BaseModel):
    """
    One problem that FastAPI found while validating a request.

    Parameters
    ----------
    loc : tuple[str | int, ...]
        Location of the value, such as ``("query", "geometry")``.
    msg : str
        Description of the problem.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore", frozen=True)

    loc: tuple[str | int, ...] = ()
    msg: str

    def describe(self) -> str:
        """
        Write the problem as text.

        Returns
        -------
        str
            Dotted location and description, such as ``query.geometry: Input should be
            a valid boolean``.
        """
        location = ".".join(str(part) for part in self.loc)
        return f"{location}: {self.msg}" if location else self.msg
