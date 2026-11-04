## Completeness (B1 item 9; gap cut > 60 s; missing = seconds inside segments without a row)

| station | file | rows | bad rows dropped | segments | total s | missing s | missing % | rule | (if cut at >10 s: segments / missing %) |
|---|---|---|---|---|---|---|---|---|---|
| BS1 | users_I796_s.csv | 889640 | 1 | 109 | 904876 | 15236 | 1.684 | STOP (>=1%) | 526 / 0.577 |
| BS2 | users_I1815_s.csv | 818205 | 0 | 73 | 830479 | 12274 | 1.478 | STOP (>=1%) | 403 / 0.514 |
| BS3 | users_I2650_s.csv | 267653 | 0 | 204 | 293923 | 26270 | 8.938 | STOP (>=1%) | 989 / 2.565 |
| BS4 | users_II816_s.csv | 586596 | 0 | 8 | 588736 | 2140 | 0.363 | fill (<1%) | 39 / 0.224 |
| BS5 | users_II1835_s.csv | 1128233 | 0 | 57 | 1135886 | 7653 | 0.674 | fill (<1%) | 305 / 0.127 |
| BS6 | users_II2650_s.csv | 1270229 | 0 | 2 | 1270806 | 577 | 0.045 | fill (<1%) | 29 / 0.003 |

## Stations built (per-minute series)

| station | full minutes | minute segments | Cmax = P99 per-minute mean | P50 | max |
|---|---|---|---|---|---|
| BS4 | 9804 | 8 | 52.83 | 26.40 | 64.30 |
| BS5 | 18891 | 30 | 125.33 | 50.08 | 157.53 |
| BS6 | 21179 | 2 | 49.59 | 26.23 | 80.62 |

## Library: 1:1 stride 60 (main)

windows 822, kept 556, rejected 266 (by mp 166, f36 79, minUE 75, nan 0; a window may fail several)
thresholds: mp in [0.6738, 0.8589] (P10,P90), f36 <= 0.1333 (P90), minUE >= 5.0 (P10)
(bs, date) groups: kept 39 (all windows 39); windows per kept group mean 14.26, min 2, max 23

| station | windows | kept | groups kept |
|---|---|---|---|
| BS4 | 160 | 68 | 8 |
| BS5 | 310 | 232 | 15 |
| BS6 | 352 | 256 | 16 |

## Library: 1:1 stride 30 (sensitivity)

windows 1631, kept 1114, rejected 517 (by mp 325, f36 159, minUE 142, nan 0; a window may fail several)
thresholds: mp in [0.6733, 0.8583] (P10,P90), f36 <= 0.1000 (P90), minUE >= 5.0 (P10)
(bs, date) groups: kept 39 (all windows 39); windows per kept group mean 28.56, min 2, max 45

| station | windows | kept | groups kept |
|---|---|---|---|
| BS4 | 315 | 133 | 8 |
| BS5 | 613 | 463 | 15 |
| BS6 | 703 | 518 | 16 |

## Library: compressed 4:1 stride 240 (contrast P)

windows 198, kept 135, rejected 63 (by mp 40, f36 19, minUE 20, nan 0; a window may fail several)
thresholds: mp in [0.6128, 0.8500] (P10,P90), f36 <= 0.0667 (P90), minUE >= 6.7 (P10)
(bs, date) groups: kept 36 (all windows 38); windows per kept group mean 3.75, min 1, max 6

| station | windows | kept | groups kept |
|---|---|---|---|
| BS4 | 38 | 17 | 7 |
| BS5 | 73 | 51 | 15 |
| BS6 | 87 | 67 | 14 |
