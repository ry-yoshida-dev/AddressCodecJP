from address_codec_jp.datasets.address_base_registry.area_position import AreaPosition
from address_codec_jp.datasets.address_base_registry.lot_entry import LotEntry
from address_codec_jp.datasets.address_base_registry.lot_position import LotPosition
from address_codec_jp.datasets.address_base_registry.lot_removal import LotRemoval
from address_codec_jp.geometry import TownPosition

type PositionRecord = AreaPosition | TownPosition | LotEntry | LotPosition | LotRemoval
