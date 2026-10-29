from collections.abc import Mapping, Sequence

type OutputValue = str | int | float | Sequence[OutputValue] | Mapping[str, OutputValue] | None
