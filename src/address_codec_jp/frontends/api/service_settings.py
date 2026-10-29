from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Self


@dataclass(frozen=True, slots=True)
class ServiceSettings:
    """
    Configuration of the web API.

    The service reads a cache prepared beforehand and never downloads while handling
    requests.

    Parameters
    ----------
    publisher : str
        Organization that processes and serves the data. The terms of use of every
        dataset require the credits to name who processed it.
    cache_directory : Path | None
        Directory of the prepared cache, or ``None`` for the default of
        ``DatabaseCache.default``, which also honors ``ADDRESS_CODEC_JP_CACHE_DIR``.
    thread_count : int
        Worker threads of a process, each with its own codec.
    max_batch_size : int
        Largest number of inputs in one batch request.
    is_coverage_required : bool
        Whether a query whose municipality has not been prepared is rejected with
        HTTP 503 instead of falling back to an enclosing area.

    Raises
    ------
    ValueError
        If ``publisher`` is blank, or ``thread_count`` or ``max_batch_size`` is not
        positive.
    """

    PUBLISHER_VARIABLE: ClassVar[str] = "ADDRESS_CODEC_JP_API_PUBLISHER"

    THREAD_COUNT_VARIABLE: ClassVar[str] = "ADDRESS_CODEC_JP_API_THREADS"
    MAX_BATCH_SIZE_VARIABLE: ClassVar[str] = "ADDRESS_CODEC_JP_API_MAX_BATCH_SIZE"
    COVERAGE_VARIABLE: ClassVar[str] = "ADDRESS_CODEC_JP_API_COVERAGE_REQUIRED"
    _TRUE_TEXTS: ClassVar[frozenset[str]] = frozenset({"1", "true", "yes"})
    _FALSE_TEXTS: ClassVar[frozenset[str]] = frozenset({"0", "false", "no"})

    publisher: str
    cache_directory: Path | None = None
    thread_count: int = 4
    max_batch_size: int = 1000
    is_coverage_required: bool = True

    def __post_init__(self) -> None:
        if not self.publisher.strip():
            raise ValueError("publisher must name the organization that serves the data.")
        if self.thread_count <= 0:
            raise ValueError(f"thread_count must be positive, got {self.thread_count}.")
        if self.max_batch_size <= 0:
            raise ValueError(f"max_batch_size must be positive, got {self.max_batch_size}.")

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]) -> Self:
        """
        Read the settings from environment variables.

        ``ADDRESS_CODEC_JP_API_PUBLISHER`` is required. ``ADDRESS_CODEC_JP_API_THREADS``,
        ``ADDRESS_CODEC_JP_API_MAX_BATCH_SIZE``, and
        ``ADDRESS_CODEC_JP_API_COVERAGE_REQUIRED`` (``true`` or ``false``) override the
        defaults; the cache directory follows ``ADDRESS_CODEC_JP_CACHE_DIR``.

        Parameters
        ----------
        environment : Mapping[str, str]
            Environment variables, usually ``os.environ``.

        Returns
        -------
        Self
            Settings with the defaults for unset variables.

        Raises
        ------
        ValueError
            If the publisher is not set, or a variable is not a valid number or flag.
        """
        publisher = environment.get(cls.PUBLISHER_VARIABLE, "")
        if not publisher.strip():
            raise ValueError(
                f"Set {cls.PUBLISHER_VARIABLE} to the organization that serves the data; "
                + "the credits of the datasets name it."
            )
        defaults = cls(publisher)
        return cls(
            publisher=publisher,
            thread_count=int(environment.get(cls.THREAD_COUNT_VARIABLE, defaults.thread_count)),
            max_batch_size=int(
                environment.get(cls.MAX_BATCH_SIZE_VARIABLE, defaults.max_batch_size)
            ),
            is_coverage_required=cls._parse_flag(
                environment.get(cls.COVERAGE_VARIABLE), default=defaults.is_coverage_required
            ),
        )

    @classmethod
    def _parse_flag(cls, text: str | None, *, default: bool) -> bool:
        if text is None:
            return default
        normalized = text.strip().lower()
        if normalized in cls._TRUE_TEXTS:
            return True
        if normalized in cls._FALSE_TEXTS:
            return False
        raise ValueError(f"{cls.COVERAGE_VARIABLE} must be true or false, got {text!r}.")
