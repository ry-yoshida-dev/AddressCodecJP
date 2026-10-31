import pytest

from address_codec_jp import (
    Address,
    AddressCodec,
    AddressCodecError,
    AddressLevel,
    AddressNotFoundError,
    AmbiguousAddressError,
    LotNumber,
    MatchTier,
    RegistryImporter,
)
from address_codec_jp.text.matching import AreaMatcher
from address_codec_jp.text.normalization import LotNumberParser, TextNormalizer


@pytest.mark.parametrize(
    ("address", "tier"),
    [
        ("台東区浅草橋1丁目", MatchTier.EXACT),
        ("網走市字大曲", MatchTier.EXACT),
        ("神恵内村赤石村字山ノ上", MatchTier.UNPREFIXED),
        ("神恵内村大字赤石村山ノ上", MatchTier.UNPREFIXED),
        ("千代田区丸ノ内1丁目", MatchTier.FOLDED),
    ],
)
def test_match_reports_loosest_name_comparison(
    codec: AddressCodec, address: str, tier: MatchTier
) -> None:
    assert codec.match(address).town_name_tier is tier


def test_match_without_town_has_no_tier(codec: AddressCodec) -> None:
    assert codec.match("台東区").town_name_tier is None


def test_ambiguous_town_lists_candidates(codec: AddressCodec) -> None:
    with pytest.raises(AmbiguousAddressError) as raised:
        _ = codec.encode("神恵内村赤石村山之上")
    assert [str(code) for code in raised.value.candidates] == ["014052-0001001", "014052-0001002"]


def test_ambiguous_municipality_lists_candidates(codec: AddressCodec) -> None:
    with pytest.raises(AmbiguousAddressError) as raised:
        _ = codec.encode("府中市")
    assert [code.level for code in raised.value.candidates] == [AddressLevel.MUNICIPALITY] * 2


def test_errors_keep_their_builtin_bases(codec: AddressCodec) -> None:
    with pytest.raises(LookupError):
        _ = codec.encode("存在しない市")
    with pytest.raises(AddressCodecError):
        _ = codec.encode("存在しない市")


def test_resolve_returns_registered_areas(codec: AddressCodec) -> None:
    address = codec.resolve("131067-0004001-2")
    assert address.town is not None
    assert (address.prefecture.name, address.town.oaza_name, address.lot) == (
        "東京都",
        "浅草橋",
        LotNumber(block=2),
    )
    assert str(address.code) == "131067-0004001-2"
    assert codec.resolve("130001").municipality is None
    with pytest.raises(AddressNotFoundError):
        _ = codec.resolve("131067-0009999")


def test_address_rejects_areas_that_do_not_contain_each_other(codec: AddressCodec) -> None:
    taito = codec.resolve("131067").municipality
    marunouchi = codec.resolve("131016-0011001").town
    assert taito is not None
    assert marunouchi is not None
    with pytest.raises(ValueError, match="not in municipality"):
        _ = Address(prefecture=taito.prefecture, municipality=taito, town=marunouchi)
    with pytest.raises(ValueError, match="require a town"):
        _ = Address(prefecture=taito.prefecture, municipality=taito, lot=LotNumber(block=1))


def test_find_returns_none_instead_of_raising(importer: RegistryImporter) -> None:
    normalizer = TextNormalizer()
    matcher = AreaMatcher(importer.database.towns, normalizer, LotNumberParser())
    found = matcher.find(normalizer.normalize("千代田区丸の内1-2-3"), None)
    assert found is not None
    assert str(found.code) == "131016-0011001-2-3"
    assert matcher.find(normalizer.normalize("存在しない市"), None) is None
    assert matcher.find(normalizer.normalize("神恵内村赤石村山之上"), None) is None
