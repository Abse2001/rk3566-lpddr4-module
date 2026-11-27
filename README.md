# RK3566 + LPDDR4 compute module (CM4 compatible)

A 6-layer compute module built around the Rockchip RK3566 (U1, LCSC C2943786) and 2 GB of SK hynix
H9HCNNNBKUMLXR-NEE LPDDR4 (U2, LCSC C21912322).

****Status: fully routed, fab files generated** (`fab/`, also `fab/tsci/` from `tsci export -f gerbers`).
CM4-compatible: two Hirose DF40C-100DP-0.4V(51) on the bottom at the CM4 positions; CAM0, DSI0 and Ethernet
are not populated (networking over USB). How it was routed: `ROUTING-PLAYBOOK.md`; issue log: `ISSUES-AND-FIXES.md`.

Full-board checks (`source/check.py`, `source/pairs.py` on `source/route/final/`):

| Check | Result |
|---|---|
| Copper clearance 0.1 mm, all 6 layers (vias on every layer) | 0 violations |
| Copper to edge / holes, via hole spacing, SMD pad to pad 0.15 mm | 0 issues |
| Via hole to other copper | below JLCPCB's 0.2 mm in places (their DFM: "Danger"; accepted on past orders) |
| Fast traces over unbroken GND (reference plane) | 0 issues |
| Connectivity (pads, traces, vias, pours) | 234 / 234 nets |
| Differential pairs P/N (0.13 mm, USB 0.25 mm) | 17 / 17 within limit |
| LPDDR4 block | re-solved with the delay-aware solver: Rockchip length rules pass; delay check (per-layer ps/mm + via barrels, `source/route/ddr_timing.py`) all CK/DQS pairs 0.0-0.1 ps; ngspice (`ddr_sim.py`) CK crossing skew 0.0 ps |
| JLCPCB SMD assembly spacing (`source/dfm_spacing.py`) | 0 pairs below the table (chip-QFN/BGA 1.0 mm, chip-chip 0.15 mm) |
| Silkscreen | lines >= 0.15 mm; text under 1.0 mm dropped (designators on the fab layer) |
| Pick-and-place rotations vs JLCPCB footprints (`source/fix-pnp.ts`) | 211 / 211 verified |

**Ordering (JLCPCB):** 6 layers, 1.6 mm, stackup JLC06161H-1080A, ENIG, via-in-pad filled and capped,
0.15 mm hole / 0.25 mm via, assembly on both sides. Before paying, check part rotations in JLCPCB's
placement preview (especially bottom side, U1, U2, U3, U4 and J1/J2) and stock of the BOM.

Still to verify by hand: RK809 auto-start when GLOBAL_EN rises and the 1.8 V before 3.3 V sequence; eMMC
VDDI capacitor; crystal load capacitors. The tscircuit viewer lists 59 courtyard overlaps: these are the
0201 decoupling capacitors under the BGA (pads 0.18 mm or more apart, above JLCPCB's 0.15 mm).

PCB](pcb.png)

## LPDDR4 block

- All 67 LPDDR4 nets between U1 and U2 are routed (both channels: CA, CS, CKE, ODT, RESET, CK pairs,
  16 DQ, 2 DMI and 2 DQS pairs per channel). They run on three signal layers: top, inner3 and bottom.
- The power and ground balls of both packages are fanned out to their planes. Every ball whose
  neighbours leave room takes a filled via in its own pad; the 0.4 mm perimeter band of the RK3566 fans
  out to vias beside it, outside the strips the DDR breakout uses.

Results from `source/route/rk-check.ts`, in full in `source/route/check-results.txt`:

| Check | Result |
|---|---|
| Connectivity | 67 / 67 |
| Copper clearance at 0.10 mm (JLCPCB 6-layer minimum is 0.09 mm) | 0 issues |
| CK and DQS P/N mismatch (limit 12 mil) | 0.0 to 0.8 mil |
| CA/CS/CKE/ODT to CK (limit 500 mil) | worst 278 mil |
| DQ/DMI to DQS within a byte (limit 600 mil) | worst 485 mil |
| DQS to CK (limit 1200 mil) | worst 329 mil |
| Vias | 133 in total, 0 to 4 per net |

The limits are the LPDDR4 rules of Rockchip's RK356x high-speed PCB design guide (Table 33).

## Stackup

JLCPCB template **JLC06161H-1080A**, 1.6 mm, FR-4 TG155:

| Layer | Use | Dielectric to the next layer |
|---|---|---|
| L1 top | DDR signals, both BGAs | 1080 prepreg, 0.0764 mm, Er 3.91 |
| L2 (inner1) | ground | core 0.6 mm |
| L3 (inner2) | power | 3313 prepreg, 0.0994 mm, Er 4.1 |
| L4 (inner3) | DDR signals | core 0.6 mm |
| L5 (inner4) | ground | 1080 prepreg, 0.0764 mm |
| L6 bottom | DDR signals | |

All traces are 0.11 mm wide. A 2-D field solve gives about 53 ohm on the outer layers (a few ohms lower
under solder mask) and 52.5 ohm on inner3. CK and DQS pairs have a 0.18 mm gap, about 100 ohm
differential. Rockchip asks for 50 ohm single-ended and 100 ohm differential.

Vias are through vias, 0.15 mm hole and 0.25 mm pad. Many sit in pads, so order them epoxy-filled and capped;
JLCPCB fills via-in-pad free of charge on 6-layer boards.

## Files

- `index.circuit.json`: the board as tscircuit circuit JSON (rendered by `source/build.tsx`).
- `imports/`: the RK3566 and LPDDR4 footprints.
- `source/route/ddr.lane.routed.json`: the routed DDR traces, as produced by the negotiated-lane solver.
- `source/route/ddr.input.json`: the routing problem (pads, power fanout, buses and length rules).
- `source/route/power.fanout.json` and `power-fan-v5.ts`: the power fanout and the script that made it.
- `source/route/run-lane.ts`: the routing run. It uses `NegotiatedLaneSolver` from the bus-lanes-solver
  `feat/negotiated-lane-solver` branch with layers top, inner3 and bottom.
- `source/route/rk-check.ts`: the independent check (connectivity, DRC, Rockchip timing).
- `source/route/route.png`: the DDR block by layer (red top, green inner3, blue bottom, grey power fanout).

Rebuild the board JSON with `bun source/build.tsx`.
