from typing import override

from address_codec_jp.text.normalization import TextNormalizer


class CountingNormalizer(TextNormalizer):
    """Text normalizer that counts how many texts it normalizes and folds."""

    def __init__(self) -> None:
        self.normalize_count: int = 0
        self.fold_count: int = 0

    @override
    def normalize(self, text: str) -> str:
        self.normalize_count += 1
        return super().normalize(text)

    @override
    def fold(self, normalized_text: str) -> str:
        self.fold_count += 1
        return super().fold(normalized_text)
