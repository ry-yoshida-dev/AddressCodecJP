from enum import Enum, auto


class NameScript(Enum):
    """
    Script of the names and lot markers in a decoded address.

    Attributes
    ----------
    KANJI
        Names as registered, e.g. ``東京都千代田区丸の内1丁目2番3号``.
    KATAKANA
        Registered katakana readings, e.g. ``トウキョウトチヨダクマルノウチ1チョウメ2バン3ゴウ``.
    """

    KANJI = auto()
    KATAKANA = auto()
