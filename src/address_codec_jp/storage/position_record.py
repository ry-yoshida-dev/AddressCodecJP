from address_codec_jp.storage.area_position import AreaPosition
from address_codec_jp.storage.lot_entry import LotEntry
from address_codec_jp.storage.lot_position import LotPosition
from address_codec_jp.storage.lot_removal import LotRemoval
from address_codec_jp.storage.town_position import TownPosition

type PositionRecord = AreaPosition | TownPosition | LotEntry | LotPosition | LotRemoval
