from address_codec_jp.domain.town_position import TownPosition
from address_codec_jp.storage.area_position import AreaPosition
from address_codec_jp.storage.lot_entry import LotEntry
from address_codec_jp.storage.lot_position import LotPosition
from address_codec_jp.storage.lot_removal import LotRemoval

type PositionRecord = AreaPosition | TownPosition | LotEntry | LotPosition | LotRemoval
