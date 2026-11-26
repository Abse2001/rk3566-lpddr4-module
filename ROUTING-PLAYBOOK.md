# How the RK3566 CM4 module was routed (playbook for other modules, e.g. AM3354)

This is the end-to-end recipe that took the RK3566 + LPDDR4 CM4-compatible module from a netlist to DRC-clean
fab files. The board is 6 layers, 40 x 55 mm, with 211 parts and 234 nets. Every script named here is in
`rk3566-module/source/`. Copy them and change only the board-specific constants: board outline, holes, SoC
position, rail names and the fast-net regex.

The final result is at `source/route/final/`:
- `check.py` exits 0;
- 234/234 nets are connected;
- 17/17 differential pairs are length-matched;
- the DDR block is byte-identical to the verified DDR routing.

The full issue log is in `ISSUES-AND-FIXES.md`.

---

## 0. The big idea

Do not route the whole board in one go with a general autorouter. Several tools were tried and failed:
- tscircuit Pipeline 9/10 found 0 routes;
- the fanout-solver escaped 35 of 116 nets.

The approach that worked is layered: each stage freezes its copper as fixed obstacles for the next one.

| Stage | What | Tool | Output |
|---|---|---|---|
| 1 | Rules + stackup decided up front | (this doc §1) | constants in every script |
| 2 | Placement with keep-outs for the DDR block and the BGA escape band | `design/place.py` | `design/placement.json`, `design/pads.json` |
| 3 | DDR block (SoC <-> RAM), routed alone, verified, then **frozen** | `NegotiatedLaneSolver` (bus-lanes-solver) via `route/run-lane.ts` | `route/ddr.lane.routed.json` |
| 4 | Power/GND ball fanout (via-in-pad) | `route/power-fan-v5.ts`, `route/fanout_bga.py` | `power.fanout.json`, `bga_vias.json` |
| 5 | Merge frozen copper | `route/fixed.py` | `route/fixed.json` |
| 6 | Everything else: negotiated-congestion grid router | `route/route.ts` | `routes*.json`, `copper*.json` |
| 7 | Pair length matching | `route/tune_pairs.py` | rewrites routes/copper |
| 8 | Strict reroute of pairs that tuning can't fix | `route/reroute.py` | rewrites routes/copper |
| 9 | Clearance repair of tiny grid-rounding misses | `route/repair.py` | rewrites copper |
| 10 | Planes: GND pours + power islands | `route/planes.py` | `planes.json` |
| 11 | Independent DRC + connectivity + reference-plane check | `check.py`, `pairs.py` | exit code 0 = pass |
| 12 | Build circuit JSON, export Gerbers/BOM/CPL | `build.tsx`, `export.ts` | `index.circuit.json`, `fab/` |

**Never re-route a frozen block.** If a later stage collides with the DDR copper, fix the later stage or the
placement, not the DDR routing.

---

## 1. Rules (JLCPCB 6-layer, cheapest options)

| Rule | Value used | Why |
|---|---|---|
| Trace / space | 0.1 / 0.1 mm (JLC min 0.09) | small margin |
| Via | 0.15 hole / 0.25 pad, through | the one paid option, needed for BGA |
| Via-in-pad | yes, filled + capped | free on 6+ layers at JLC |
| SMD pad to pad (different nets) | 0.15 mm | JLC assembly rule |
| Copper to board edge / holes | 0.25 mm (router uses 0.3) | |
| Via hole to hole | 0.2 mm edge to edge | |
| Finish | ENIG | BGA/WLCSP pads of 0.2–0.25 mm |
| Stackup | JLC06161H-1080A | L1 sig, L2 GND, L3 PWR, L4 sig, L5 GND, L6 sig (Rockchip HDG §3.1) |

The router uses GAP = 0.1 + 0.012 mm. The 0.012 mm is grid slack, so the exact checker always sees at least 0.1 mm.

Layer use, following the vendor hardware design guide:
- **top, inner3, bottom:** signals.
- **inner1, inner4:** solid GND, the reference planes for top and bottom.
- **inner2:** power islands, one per core rail.
- **Exception:** slow nets (≤0.2 mm wide) may use inner1/inner4/inner2, but only where they don't break a fast
  trace's reference (see §6).

---

## 2. Placement (`design/place.py`)

Things that mattered:
- **Fix the board frame first** (CM4: holes at (0,0), (33,0), (0,-48), (33,-48); J1/J2 at x = -0.46 / 33.46,
  y = -26.5, bottom side). Check pin 1 orientation: a KiCad y-down to y-up conversion silently mirrored the
  connector once.
- **Keep-out boxes** that placement must respect:
  - `top_block` / `bottom_block`: the frozen DDR traces and vias on top and bottom, plus the eMMC field.
  - `escape_band`: 2.5 mm south and 1.5 mm east/west of the SoC ball field. Without it, decaps land where the
    BGA escape has to go.
- **Under-BGA decaps** sit on the bottom, on the power via-in-pad sites.
- **Leave feed corridors** for each core rail from its regulator to the SoC power balls (inner2 islands must
  be one piece). Placement bugs found by `planes.py` included:
  - a cap sitting in a corridor;
  - an inductor cutting VCC_DDR off;
  - PMIC thermal vias inside another rail's island.
- Drop features you don't need before routing; it's the cheapest congestion fix. Here CAM0, DSI0 and Ethernet
  were dropped (`design/make-cm4-map.py`: those CM4 pins are NC).

---

## 3. DDR block: route alone, verify, freeze

1. Build the DDR problem (`route/ddr.input.json`): pads, the power fanout as obstacles, buses (byte lanes, CA)
   and the length rules from the vendor HDG.
2. Run `NegotiatedLaneSolver` (bus-lanes-solver, `feat/negotiated-lane-solver`) via `route/run-lane.ts`:
   - layers top, inner3, bottom;
   - trace w 0.11, gap 0.1, pairGap 0.18;
   - via 0.25/0.15 with via-in-pad.
   It checkpoints after each stage, so a container restart resumes.
3. Verify with `route/rk-check.ts`: connectivity, clearance, and the Rockchip LPDDR4 timing table:
   - CK/DQS P/N;
   - CA to CK;
   - DQ to DQS within a byte;
   - DQS to CK.
4. Save it as `ddr.lane.routed.json` in **SoC-local coordinates**; `fixed.py` moves it to the board position.
   From then on it is fixed copper. A check at the end proves it is unchanged: compare all `DDR_*` traces and
   vias between the reference and the final `copper.json`.

---

## 4. Power fanout (via-in-pad)

- `power-fan-v5.ts`: fans the supply/GND balls of the DDR corner out to vias.
- `fanout_bga.py`: puts a via in the pad of every remaining supply/GND ball of the SoC inner grid and the eMMC,
  where it clears all other copper by 0.1 mm on every layer.
- `fixed.py` merges the DDR block and the fanout into `fixed.json`. It **drops** any fanout via that comes
  closer than ball radius + via radius + gap to another net's ball. A stale ball map once put power vias on
  signal balls.

Inner-ring signal balls escape exactly as the Rockchip guide says:
- the outer 2 rings escape on top;
- inner rings use vias in the channels between balls, then route out on inner3 or bottom.
The grid router does this automatically, because via-in-pad is allowed on signal balls.

---

## 5. The negotiated-congestion router (`route/route.ts`)

This is a PathFinder-style router, the same idea as FPGA routers:
- **Grid:** 0.05 mm over the whole board, through vias.
- **Clearance:** exact shape stamping. A trace centre may not come within gap + half width of other copper; a
  via centre may not come within gap + via radius.
- **Nets are trees:** each remaining terminal joins the copper already placed for the net.
- **Plane nets** (GND, core rails) only need each pad joined to a via; the planes connect the vias.
- **Each pass:** every net in conflict is ripped up and re-routed with A*. The cost is length + via cost +
  present-congestion price `pres` + accumulated history cost. `pres` grows by PG each pass up to PMAX, so
  shared cells get more expensive until nets give way.

### Features that were needed

All of these are general, with no per-net special cases:

| Feature | Env | Problem it solved |
|---|---|---|
| Best snapshot + rollback after STALL passes without improvement | `STALL` | negotiation diverging; output is always the best state seen |
| Endgame clusters: re-route groups of conflicting nets strictly ("hard": zero conflicts allowed), then priced fallback; keep only if the **whole board** improves; repeat rounds | `EG_TRIES`, `EG_CAP`, `EG_ROUNDS` | last 5–50 conflicts never clearing; judging only the moved nets made the total worse |
| `pres` reset after the endgame | `PRESET` | resume negotiation without old price spikes |
| Bounding-box search with growing margin | `BOX` | speed |
| Slow nets on GND layers (inner1/inner4) at extra cost, never within R_REF of a fast trace on the adjacent outer layer, never under DDR copper | `GND_SIG=1`, `GND_COST=2` | more room without breaking reference planes |
| Same, also under the SoC field | `GND_SIG_BGA=1` | escape congestion under the BGA |
| Slow nets on inner2 outside the power-island corridors (corridors widened by KEEP) | `INNER2_OPEN=1`, `KEEP` | more room; islands still one piece |
| Fast nets (regex `^(HDMI_TX_[CD]\|MIPI_\|PCIE20_\|USB_OTG0_D\|EMMC_\|CM4_SD_)`) never use GND/power layers | built in | reference integrity |
| Neck zones (BGA, fine-pitch): wide traces drawn at 0.1 mm and stamped at signal width | built in | phantom conflicts the endgame could never clear |
| **Differential pairs.** The lead (P) routes with its follower lifted and pays for the follower's room. The follower (N) is confined to FOLLOW_R of the lead's path, or FOLLOW_T of its own terminals, and never enters the lead's keep-out. A follower that can't fit is "decoupled": penalty + history on the lead | `FOLLOW_R=0.6`, `FOLLOW_T=2` | P/N wandering apart (31 mm skew) |
| Pairs may enter neck zones only within PAIR_ESC of their own balls | `PAIR_ESC=3.0` | pairs crossing under the SoC. 2 mm was too small: the deepest pair ball is 2.5 mm in |
| Polish / renegotiate a finished routing | `POLISH=routes.json`, `RENEG=1`, `RENEG_MIN` | (weak in practice, see §8) |

### The run that worked (run 61)

```bash
cd source/route
GND_SIG=1 GND_SIG_BGA=1 INNER2_OPEN=1 GND_COST=2 SEED=5 OUT=_61 bun route.ts > run61.log
```

- Run several seeds in parallel (`SEED=1..6`, distinct `OUT=`), and keep the one with the lowest best conflicts.
- Kill runs by PID or by their `OUT`. **Never** use `pkill -f "bun route.ts"`: it kills every run.
- Run 61 reached 0 conflicts after 73 passes; `repair.py` then cleared the last grid-rounding misses.

---

## 6. Reference-plane rule (the check that keeps 6 layers honest)

A fast trace on top (or bottom) must have unbroken GND under it on inner1 (or inner4). Concretely, no non-GND
copper on that layer within w/2 + 3h of the trace edge, where h = 0.0764 mm prepreg. It is enforced in:
- the router (GND_SIG);
- `tune_pairs.py` (bumps avoid the zone);
- `reroute.py`;
- `check.py` (the final authority).

---

## 7. Pair length matching (`route/tune_pairs.py`)

For each pair, the shorter member gets square bumps (accordion) on its longest straight runs, bulging away
from its partner, until the lengths agree within 0.05 mm:
- a bump is kept only if it clears all other copper by 0.1 mm and the reference zone;
- the limits checked afterwards by `pairs.py` are 0.13 mm (0.25 mm for USB).

```bash
ROUTES=.../routes.json COPPER=.../copper.json AMPS=1.2,0.9,0.7,0.55,0.45,0.35,0.25,0.15 MIN_L=0.35 python3 route/tune_pairs.py
```

Larger amplitudes (up to 1.2 mm) and shorter minimum runs (0.35 mm) fixed most pairs. Tuning **cannot** fix a
pair whose members took completely different paths (4–5 mm skew); see §8.

---

## 8. Strict pair reroute (`route/reroute.py`): the step that finished the board

Problem: under the SoC only one trace fits per channel between balls, so a pair's N member sometimes wandered
across top/bottom while P ran on inner3, giving 4–5 mm of skew. Renegotiating those pairs inside `route.ts`
**diverged** (400–1500 conflicts). The reason is that the grid view of a finished routing already counts
~1400 conflict cells that the exact DRC accepts, so the negotiation restarts far from its own optimum.

What worked was a small strict A* router on the exact finished copper:
- rip up the named nets only;
- 0.05 mm grid; a cell is free when its centre keeps 0.1 + w/2 from other copper (exact shapely geometry),
  from the board edge and holes, and from the reference-zone rule;
- a via needs that on all 6 layers, plus 0.2 mm hole-to-hole;
- zero conflicts accepted, ever;
- a pair member is attracted to its partner: steps off the partner's pitch cost 1.6x.

```bash
ROUTES=r.json COPPER=c.json M=0.002 VIA_COST=0.6 \
  NETS=MIPI_CSI_RX_D2P,MIPI_CSI_RX_D2N,MIPI_DSI_TX1_CLKP,MIPI_DSI_TX1_CLKN python3 route/reroute.py
```

- **Order matters:** route P first, then N. Try both orders and via costs (it takes seconds) and keep the
  smallest skew.
- `M` is the grid safety margin. 0.012 mm was too strict for one escape and 0.002 mm passed; the exact
  `check.py` afterwards is what guarantees correctness.
- Result: skews went 4.3 → 0.7 mm and 5.1 → 2.3 mm, then `tune_pairs.py` matched both exactly.

---

## 9. Repair, planes, check

```bash
COPPER=c.json python3 route/repair.py                      # nudges traces ≤0.03 mm away from a too-close obstacle, keeps only clean moves
COPPER=c.json PLANES_OUT=p.json python3 route/planes.py    # GND pours on inner1/inner4; one island per core rail on inner2
COPPER=c.json PLANES=p.json python3 check.py; echo $?      # must print 0
python3 pairs.py r.json                                    # every pair "OK"
```

`planes.py` details that mattered:
- Corridors joining each rail's vias are claimed first (pre-claimed from `corridors.json`), shortest first.
  The remaining cells go to the nearest island.
- Islands keep 0.12 mm from each other, plus clearance from foreign vias and inner2 traces.
- Footprint vias (e.g. PMIC thermal pads) count as foreign copper.
- Each rail must report `pieces: 1, unjoined: 0`. If not, the cause is almost always placement (a part or a
  via in the corridor). Fix placement; don't relax the cut.

`check.py` is independent of the router: it uses shapely on the final geometry. It checks:
- clearance on every layer (vias on all layers);
- edge and holes;
- via-hole spacing;
- SMD pad-to-pad ≥0.15 mm;
- the reference-plane rule;
- connectivity through pads, traces, vias and pours.
**Trust only this**, not the router's own conflict count.

---

## 10. Build and export

```bash
F=$PWD/route/final
COPPER=$F/copper.json PLANES=$F/planes.json bun build.tsx   # writes ../index.circuit.json
bun export.ts                                              # writes ../fab: gerbers/, bom.csv, cpl.csv, cm4-pinmap.csv
```

Afterwards:
- `export.ts` ends with `fix-pnp.ts`. It looks up each LCSC part's JLCPCB/EasyEDA footprint through the
  tscircuit parts engine and compares where pin 1 sits on that footprint and on ours. Bottom-side parts are
  un-mirrored first. It writes `pin1_location` and `supplier_pin1_location_map` into `index.circuit.json` and
  corrected rotations into `cpl.csv`. Without that metadata, `tsci export -f gerbers` warns "cannot verify
  jlcpcb pick-and-place rotation" for every part.
- For a tscircuit-CLI fab zip: `tsci export index.circuit.json -f gerbers -o fab/tsci/<name>.zip`. It must
  print 0 rotation warnings.
- Re-run `check.py` on the final files.
- Confirm that every `source_component` appears in both the BOM and the CPL.
- Zip `fab/gerbers` for the JLC upload.

---

## 11. Checklist to reuse on another module (AM3354, etc.)

1. Decide the stackup and rules first, and put the constants in every script.
2. Place with keep-outs: memory block, BGA escape band, rail corridors. Fix the connector frame and pin-1
   orientation.
3. Route the memory block alone with `NegotiatedLaneSolver`, check its timing, and freeze it in SoC-local
   coordinates.
4. Do the power via-in-pad fanout, then `fixed.py` (drop vias that hit foreign balls).
5. Run `route.ts` with several seeds:
   - `GND_SIG=1 GND_SIG_BGA=1 INNER2_OPEN=1 GND_COST=2`;
   - adapt the `FAST` regex, `PLANE_PWR`, the board box and `HOLES` to the new board;
   - keep the best run.
6. `tune_pairs.py`. If a pair remains with more than about 1 mm of skew, run `reroute.py` on that pair (P then
   N), then `tune_pairs.py` again.
7. Run `repair.py` → `planes.py` → `check.py` (exit 0) → `pairs.py` (all OK).
8. `build.tsx` → `export.ts` → verify BOM/CPL counts → zip the Gerbers.
9. Prove the memory block is unchanged (diff its traces and vias against the frozen file).
10. Log every issue and fix in `ISSUES-AND-FIXES.md` as you go.

### Pitfalls we hit (save yourself the time)

- **Coordinates:** a KiCad y-down source mirrored the connector. Always plot the placement and check pin 1.
- **Stale ball map:** this put power vias on signal balls. Regenerate pads from the final ball map and let
  `fixed.py` drop bad vias.
- **Overwritten circuit JSON:** a dry build overwrote `index.circuit.json`. Use the `CIRCUIT=` env for
  experiments.
- **Endgame judging:** judge the endgame on the whole-board conflict count, never on the moved nets only.
- **Pair rules:** don't let differential pairs wander through a BGA field: enforce PAIR_ESC and the follow
  corridor.
- **Starting point for fixes:** don't renegotiate from a finished routing (see §8). Use the strict rerouter
  for the last few nets.
- **Cheapest congestion fix:** drop unneeded interfaces before routing.
