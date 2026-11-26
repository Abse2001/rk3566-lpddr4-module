# JLCPCB 6-layer rules: their limits vs this module

Sources were read on 2026-11-26:
- [PCB capabilities](https://jlcpcb.com/capabilities/pcb-capabilities)
- [Via covering](https://jlcpcb.com/help/article/pcb-via-covering)
- [Impedance / stackups](https://jlcpcb.com/impedance)
- [SMD minimum spacing (assembly)](https://jlcpcb.com/help/article/minimum-spacing-for-smd-components)

The pages give no prices. "Costs more" below is JLCPCB's own wording. Check the final price in their quote tool.

## Fabrication

| Item | JLCPCB limit (6 layers, 1 oz) | Free / extra | This module | Checked by |
|---|---|---|---|---|
| Trace / space | 0.09 / 0.09 mm (3.5 mil); 3 mil allowed in BGA fan-outs | free | 0.1 / 0.1 mm (DDR traces 0.11 mm) | `check.py` (0.1 mm) |
| Via hole / via pad | min 0.15 / 0.25 mm. "0.1 or 0.15 mm hole: costs more"; "0.2–0.25 mm hole with pad < 0.45 mm: costs more". Free sizes: 0.3 / 0.4 mm, or 0.2–0.25 mm holes with a ≥0.45 mm pad | **0.15/0.25 costs more** | 0.15 / 0.25 mm everywhere. Needed: a via in a 0.65 mm-pitch BGA pad, and the 0.5 mm eMMC field | — |
| Via-in-pad (epoxy or copper filled, capped) | the default process on 6+ layers; vias 0.15–0.55 mm; "resin filling … for free" on 6+ layers | **free** | used under the RK3566, eMMC, LPDDR4 and RK809 | — |
| Via hole to hole | 0.2 mm | free | ≥0.2 mm | `check.py` |
| **Via hole to other copper** (track, pad, pour; inner layers too) | **0.2 mm** | free | the old routing had ~2,000 spots at 0.15–0.2 mm; the router, `tune_pairs`, `repair` and `reroute` now enforce 0.2 mm, and `check.py` checks it | `check.py` (new) |
| Pad to track | 0.1 mm (0.09 at BGA pads) | free | 0.1 mm | `check.py` |
| SMD pad to pad (different nets) | 0.15 mm | free | 0.15 mm | `check.py` |
| BGA pad | min 0.2 mm; 0.2–0.25 mm pads need ENIG | — | RK3566 balls 0.22 mm, SYR837 0.208 mm → ENIG | — |
| Annular ring | PTH: 0.15 mm min, 0.2 mm recommended | — | through-hole parts: none. Vias are the stated 0.15/0.25 pair | — |
| Copper to routed edge | 0.2 mm | free | 0.25 mm (router 0.3 mm) | `check.py` |
| Solder mask bridge | 0.10 mm (green, 1 oz); 0.13 mm for black/white | free (green) | green | — |
| Silkscreen | line ≥0.15 mm, text ≥1.0 mm high, 0.15 mm from pads | free | reference designators | — |
| Surface finish | HASL is **not available** on 6+ layers: ENIG or OSP | ENIG price not stated | **ENIG** (needed for the 0.2 mm BGA pads) | — |
| Thickness | 0.4–4.5 mm; 6-layer stackups at 1.2 / 1.6 / 2.0 mm | — | 1.6 mm | — |
| Copper | outer 1 / 2 oz; inner 0.5 (default) / 1 / 2 oz | default | outer 1 oz, inner 0.5 oz (JLC06161H-1080A) | — |
| Stackup | JLC06161H-1080A: 1080 prepreg 0.0764 mm under the outer layers, 3313 0.0994 mm in the middle, 0.6 mm cores | — | JLC06161H-1080A | — |
| Impedance control | supported on 6 layers, ±10 % (±5 % on request) | price not stated | traces sized for 50 Ω / 100 Ω on this stackup; order with impedance control | — |

## Assembly (SMD spacing table, same side, edge to edge)

| Pair | JLCPCB | This module (old routing) | This module (re-placed) |
|---|---|---|---|
| chip–chip (0201 / 0402 / 0603) | 0.15–0.18 mm | min 0.18 mm | ≥ table (`place.py` enforces it) |
| chip–QFN (RK809) | 1.0 mm | 14 caps at 0.45–0.78 mm | ≥1.0 mm |
| chip–BGA (SYR837, RK3566, eMMC, LPDDR4) | 1.0 mm | 6 parts at 0.43–0.82 mm (SYR837) | ≥1.0 mm |
| chip–SOT | 0.2 mm | ok | ok |
| BGA–BGA | 2.0 mm | ok | ok |

Power inductors and crystals have no row in the table. They are treated as chip parts of their size, so they
keep 1.0 mm from the RK809.

## What costs extra on this order

1. **0.15/0.25 mm vias.** No way around this: a free 0.3/0.4 mm via does not fit in a 0.65 mm-pitch BGA pad.
2. **ENIG.** HASL does not exist on 6 layers, and the 0.2 mm BGA pads need ENIG anyway.
3. **Impedance control**, if selected (recommended for DDR, HDMI, MIPI and PCIe).
4. **Assembly on both sides** (the 0201 caps under the BGA are on the bottom).

Everything else uses JLCPCB's default or free options: via-in-pad filling, 1 oz / 0.5 oz copper, a standard
stackup, 1.6 mm thickness and green mask.
