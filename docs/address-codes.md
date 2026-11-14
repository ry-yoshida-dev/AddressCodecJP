# Address codes

```
{lg_code}[-{machiaza_id}[-[p]{block}[-{residence}[-{branch}]]]]
```

| Code | Level | Address |
| --- | --- | --- |
| `130001` | Prefecture | 東京都 |
| `131016` | Municipality | 東京都千代田区 |
| `131016-0011000` | Town (oaza) | 東京都千代田区丸の内 |
| `131016-0011001` | Town (chome) | 東京都千代田区丸の内1丁目 |
| `131016-0011001-2` | Block | 東京都千代田区丸の内1丁目2番 |
| `131016-0011001-2-3` | Residence | 東京都千代田区丸の内1丁目2番3号 |
| `131016-0011001-2-3-4` | Residence | 東京都千代田区丸の内1丁目2番3-4号 |
| `113247-0001000-p124` | Block (parcel) | 埼玉県入間郡三芳町竹間沢124番地 |
| `113247-0001000-p124-1-1` | Residence (parcel branch) | 埼玉県入間郡三芳町竹間沢124番地1の1 |

- `lg_code`: local government code, check digit validated.
- `machiaza_id`: ABR town ID; the last three digits are the chome or koaza part, and `000` marks an oaza. An oaza that the registry lists only by its chome has no lot numbers of its own. A town ID whose first four digits are `0000` has no oaza and lies directly in its municipality.
- Lot numbers: residence indication (住居表示) numbers are plain; land parcel (地番) numbers start with `p`. A town numbered by residence indication keeps its land parcels, so `-2-3` and `-p2-3` are different places. Up to three numbers are encoded (the ABR `rsdt_num2` and `prc_num3`).
- A residence is enclosed by its block, but a land parcel branch (`p123-9`) is a parcel of its own split off from `p123`, so both are enclosed directly by their town.
- Text is encoded in the numbering system of its town. Where a town uses both, `番地` selects land parcels and `番` with `号` residence indication. With lot verification, the other system is used when the numbers are registered only there.
- Building names, floors, and room numbers are not encoded; they are returned as `remainder`. A third hyphenated number (`2-3-405`) stays in the remainder unless lot verification finds it registered as a lot.
- Shapes are JGD2011 GeoJSON MultiPolygons, exterior rings counterclockwise and holes clockwise (RFC 7946).
