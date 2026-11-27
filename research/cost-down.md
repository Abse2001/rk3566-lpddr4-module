# BOM cost-down search (JLC parts API, 2026-11-27, unit prices at qty 1)

BOM total: $114.63 per board. Biggest lines: RAM $63.42, eMMC $24.35, RK3566 $13.96, 2x DF40 $7.37, RK809 $2.39.
20 extended part types: JLC's $3 setup fee each, per order.

| Line | Now | Option | Price | Saves/board | Stock | Change needed | Footprint check |
|---|---|---|---|---|---|---|---|
| CM4 headers x2 | C6021443 Hirose $3.68 | XYECONN XY-100DP-DF40C C53200820 | $1.02 | $5.33 | 4950 | none; mating test | 104/104 pads |
| | | G-Switch GT-B0403MSV11 C42376235 | $1.53 | $4.32 | 874 | none; mating test | 104/104 pads |
| eMMC 8 GB | Kioxia C7509349 $24.35 | Samsung KLM8G1GETF-B041 C499918 (8 GB) | $20.42 | $3.93 | 541 | none (JEDEC 153-ball) | EasyEDA footprint did not align; check |
| | | BIW BWCTAQK11X32G C55061850 (32 GB) | $25.52 | -$1.17 (4x storage) | 58 | none | 153/153 |
| | | FORESEE FEMDNN064G-C9A61 C49284704 (64 GB) | $26.04 | -$1.69 (8x storage) | 270 | none | 153/153 |
| RAM 2 GB | SK hynix LPDDR4 C21912322 $63.42 | Samsung K4U6E3S4AA-MGCL C2920249 (LPDDR4X 2 GB) | $50.70 | $12.71 | 37 | 0.6 V VDDQ rail for U2 | 200/200 |
| | | BIW BWCC2X32N2A-16G-X C54770668 (LPDDR4X 2 GB) | $43.21 | $20.20 | 52 | 0.6 V VDDQ rail | no JLC footprint |

Rejected: DDR4 (2x K4A8G165WG $36.76 = $73.52, dearer and a full DDR redesign); 1 GB LPDDR4 (must be >= 2 GB);
RK809-9/-5A (cheaper by $0.13-0.86, different factory voltage presets); RK3566 (single source);
basic-library passives (no basic 0201 MLCCs or matching values found).

## Applied (branch local/cost-down, now the main board)

RAM -> Samsung K4U6E3S4AA-MGCL (LPDDR4X), eMMC -> Samsung KLM8G1GETF-B041, headers -> XYECONN XY-100DP-DF40C,
plus a TLV75801 0.6 V LDO (C2877852, $0.12) and 5 passives for VDDQ. BOM $114.63 -> $92.81 per board (-$21.83).
Stock at the time: RAM 37, eMMC 441, headers 4950. ngspice at 0.6 V swing: `ngspice-ddr-lpddr4x-*.txt`
(timing unchanged: worst eye 360 ps of 473 ps at 2112 MT/s, 205 ps of 321 ps at 3120 MT/s).
