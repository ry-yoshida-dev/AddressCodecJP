# Address codes

```
{lg_code}[-{machiaza_id}[-{block}[-{residence}]]]
```

| Code | Level | Address |
| --- | --- | --- |
| `130001` | Prefecture | 東京都 |
| `131016` | Municipality | 東京都千代田区 |
| `131016-0011000` | Town (oaza) | 東京都千代田区丸の内 |
| `131016-0011001` | Town (chome) | 東京都千代田区丸の内1丁目 |
| `131016-0011001-2` | Block | 東京都千代田区丸の内1丁目2番 |
| `131016-0011001-2-3` | Residence | 東京都千代田区丸の内1丁目2番3号 |

- `lg_code`: local government code, check digit validated.
- `machiaza_id`: ABR town ID; `000` as the chome part is an oaza listed only by chome, and never carries lot numbers.
- Building names, floors, and room numbers are not encoded; they are returned as `remainder`.
- Shapes are JGD2011 GeoJSON MultiPolygons, exterior rings counterclockwise and holes clockwise (RFC 7946).
