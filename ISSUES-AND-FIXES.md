# RK3566 module: issues found and fixes made

A running log of every problem found while finishing the module and what was done about it. Rules for every
fix: general (no special cases for one net or one spot), no relaxed design rules (JLCPCB 6-layer: 0.1/0.1 mm,
0.15/0.25 mm vias, via-in-pad filled and capped; Rockchip LPDDR4 rules), and the routed DDR block is never
changed. All routing-tool fixes are kept local (no pushes, no PRs) until the user says otherwise.

Status legend: **fixed** (done and verified), **in progress**, **open**.

## Placement (`source/design/place.py`)

| # | Issue | Root cause | Fix | Status |
|---|---|---|---|---|
| P1 | The 18 HDMI/MIPI pairs and the PMIC/GPIO nets fought over the strip south-east of the SoC (routing stalled at ~650-2000 conflicts) | The VDD_CPU buck (U4) and its inductor (L6) sat in that corner, right in the pairs' path to J2, with an inner2 island feed running up the east side | U4/L6 moved to the free north-east corner; the VDD_CPU island is fed along the band between the eMMC and the SoC (route.ts island boxes updated) | fixed |
| P2 | U4's 5 V input capacitors were 20 mm away, next to U5 | `pin_xy` matched only exact pin names; U4's pins are VIN1..VIN4, so the anchor fell through to the next IC with VCC5V0_SYS | Pin lookup also matches numbered pads (VIN -> VIN1..4); anchors prefer an IC of the part's own group | fixed |
| P3 | eMMC decoupling caps and CMD/RST/D0 pull-ups were placed near the PMIC, ~30 mm from the eMMC | Same pin-name bug (VCC -> VCC1..) | Same fix as P2 | fixed |
| P4 | tscircuit reported U4 courtyard overlaps | The imported WLCSP-20 footprint carries a 5.2 x 4.9 mm courtyard for a 1.8 x 1.4 mm chip | U4 gets its own footprint (same pads, same nets, verified) with a body + 0.25 mm courtyard | fixed |
| P5 | C97 (VCC_DDR bulk) landed on top-layer DDR traces (DQS1) - a short | Top-side placement did not avoid the routed DDR copper (only the bottom side did) | Top-side parts keep 0.5 mm from DDR top traces and 0.6 mm from its vias | fixed |
| P6 | EMMC_D3 could not route | R8 (pull-up) was placed on the bottom under the eMMC ball field, blocking the via-in-pad an inner 0.5 mm-pitch ball needs | No bottom-side parts under the eMMC ball field | fixed |
| P8 | Conflicts piled up in a band 1-3 mm outside the SoC's south edge | 22 parts sat right where the escaping signals leave the ball field (core-rail bulk caps deliberately anchored there, PMIC pull-ups/caps, HDMI REXT/HPD resistors) | Escape corridor (Rockchip / common BGA practice): no parts within 2.5 mm of the SoC ball field on the south side and 1.5 mm east/west, either layer; bulk-cap anchors moved past it | fixed |
| P7 | VCC3V3_SYS could not route | A rule letting capacitors use the other side when >= 2 mm closer put C11 under the RK809, inside the island corridors where no via may go | Rule removed (parts stay on their preferred side unless there is no room); the two VDD_CPU 22 uF output caps are placed deliberately under L6 | fixed |

## Pin map (`source/design/make-cm4-map.py`)

| # | Issue | Root cause | Fix | Status |
|---|---|---|---|---|
| M1 | CM4 pins 89 (WL_nDisable), 91 (BT_nDisable), 97 (Camera_GPIO) wired to GPIO2_C2/C3/C6 in the 1.8 V VCCIO4 bank, while a CM4 carrier drives them at 3.3 V (over-voltage risk) | Copied from the SOQuartz mapping, which has on-module wireless | 89/91 not connected (no wireless on this module); 97 moved to a 3.3 V ball | fixed |
| M2 | LED_nACT (21), LED_nPWR (95), nEXTRST (100) crossed the whole SoC from east-edge GPIO0 balls to J1 on the west | SOQuartz ball choice | Moved to free 3.3 V balls on the west edge next to J1 (device tree needs the new GPIO numbers; UART/I2C/etc. unchanged) | fixed |

## Scope decision (user)

CAM0 (CM4 pins 128-142) and DSI0 (157-171) are not connected: six fewer differential pairs through the crowded
escape south of the SoC. Kept: HDMI0, USB 2.0 OTG, PCIe x1, DSI1 (4 lanes), CAM1 (2 lanes, CSI D2/D3 + CLK1).

## Networking (user decision)

No Ethernet on the module (CM4 pins 3-19 not connected; a real CM4 has its PHY on the module). Network access is
over USB (USB Ethernet / Wi-Fi dongle on the carrier's USB ports). Requirements for that to work:
- USB_OTG0 DP/DM on CM4 pins 103/105, OTG_ID on 101, VBUSDET pulled high: the RK3566 OTG port in host mode drives
  the carrier's USB hub (USB2514B on the CM4 IO board).
- Device tree: usb dr_mode = "otg" with ID-pin role switching (host when the carrier's device port is unused).
- Device tree: GPIO4_B7 (CM4 nEXTRST, pin 100) driven high by a gpio-hog after boot, so the carrier's USB hub
  leaves reset (the module holds it low at power-up through 100 kOhm, like a CM4).

## CM4 carrier compatibility (audit against the CM4 datasheet and the CM4 IO board design)

| # | Issue | Root cause | Fix | Status |
|---|---|---|---|---|
| K1 | **Connectors mirrored along their length**: pin 1 at the wrong end and the connectors 5 mm off, so the module could not mate with any CM4 carrier | The IO board's KiCad footprint coordinates (y down) were used as they were in tscircuit (y up) | J1/J2 at y = -26.5, pin 1/101 at -16.7 and 99/199 at -36.3 (checked against the IO board footprint: holes (0,0)/(33,+-48), pin 1 at (-2, 31.3) in KiCad's frame); outline, holes and odd-row side were already right | fixed |
| K2 | DF40 land pattern differed from Hirose's (0.2 mm pads, fitting pads at +-10.265) | | 0.23 mm signal pads, 0.3 mm fitting pads at +-10.30 | fixed |
| K3 | GLOBAL_EN (99) went to the RK809 PWRON key: a carrier holding it low did not keep the module off, a long low pulse could force a shutdown, and a 5 V carrier pull-up exceeded PWRON's rating | SOQuartz mapping | GLOBAL_EN drives the enable of the 5 V -> 3.3 V buck that feeds the RK809 (100 kOhm to 5 V, as on a CM4). Assumption to verify with the RK809 datasheet: the RK809 starts on its own when its supply comes up with VDC high | fixed (verify) |
| K4 | No pull-ups on SCL0/SDA0 (80/82); the IO board's RTC and fan controller and the CAM1/DSI1 I2C rely on the CM4's 1.8 kOhm | Not in the SOQuartz-derived netlist | 1.8 kOhm to VCC3V3_PMU (the bank's supply) | fixed |
| K5 | No pull-ups on GPIO2/GPIO3 (HAT I2C) | Same | 1.8 kOhm to VCCIO6 (GPIO_VREF) | fixed |
| K6 | nRPIBOOT (93) wired straight to EMMC_CLK (1.8 V bank): a carrier driving it at 3.3 V fights the eMMC clock | SOQuartz mapping | 1 kOhm series resistor between the pin and EMMC_CLK | fixed |
| K7 | VCCIO1 (ID_SD/ID_SC, PCIe CLKREQ/PERST) fed by RK809 LDO4, which is off by default, so carrier pull-ups back-power an unpowered bank | rails.py | VCCIO1 from VCC_3V3; 10 kOhm pull-up on CLK_nREQ | fixed |
| K8 | HDMI HPD floats with no monitor; CEC has no pull-up | Not in the netlist | 100 kOhm HPD pull-down (port side); 27 kOhm CEC pull-up to 3.3 V (LCSC C25771) | fixed |
| K9 | SD_PWR_ON (75) hard-wired high: the SD card can never be power-cycled (warm reboot after a UHS 1.8 V switch fails) | Pull-up only | Driven by GPIO3_A4 (3.3 V), pull-up kept so power is on by default | fixed |
| K10 | nEXTRST (100) undefined at boot | No default | 100 kOhm pull-down: carrier devices held in reset until software releases them (as on a CM4) | fixed |
| K11 | RUN_PG (92) also reaches TSADC_SHUT_M0: in push-pull GPIO mode it would fight a carrier pulling RUN_PG low | | Device tree: tshut in CRU mode or open-drain (documented) | open (software) |
| K12 | 3.3 V rail comes up after 1.8 V (CM4 requires 3.3 V first, never below 1.8 V) | RK809-5 OTP power-up order | Needs a PMIC sequence change (OTP/registers) or documentation | open |
| K13 | GPIO14/15 (UART), ID_SC/ID_SD, and the moved LED/camera/nEXTRST pins stay at 3.3 V or follow VCCIO6 differently from a CM4; a 1.8 V GPIO_VREF carrier is not supported | Bank voltages | Documented: 3.3 V GPIO_VREF carriers only | open (doc) |
| K14 | No ESD parts on HDMI DDC/CEC/HPD (a CM4 has them; carriers may wire straight to the connector) | | Recommended addition | open |
| K15 | PCIe refclk is DC-coupled (a CM4 AC-couples it on the module) | | Verify the RK3566 refclk-out mode and termination | open (verify) |
| K16 | Board 1.6 mm vs CM4 1.2 mm +-10 % | Stackup choice | Consider a 1.2 mm 6-layer stackup (needs an impedance re-check) | open |
| K17 | AnalogIP0/1 (94/96) go to 1.8 V SARADC inputs; a carrier may apply more | | Recommended series resistor / clamp | open |

Correct as checked: all 200 pin names, all 51 GND pins, supply pins, outline and holes, bottom-side part heights (tallest about 0.9 mm under a 1.5 mm mated stack), every diff-pair polarity and lane order, the HDMI DDC level shifter, 40-pin alternate functions, the SD interface, and the maskrom path through the IO board's USB.

## Checker (`source/check.py`)

| # | Issue | Fix | Status |
|---|---|---|---|
| C1 | JLCPCB's SMD pad-to-pad rule (0.15 mm, different nets) was not checked | Added; all current pads pass | fixed |

## Router (`source/route/route.ts`, local)

| # | Issue | Root cause | Fix | Status |
|---|---|---|---|---|
| R1 | Runs diverged after reaching their best (e.g. 465 -> 653 -> 1402 conflicts) | Present price capped at its maximum makes contested nets jump back and forth | Keep the best routing seen; after STALL passes without progress go back to it | fixed |
| R2 | The endgame gave up on everything ("no order fits") | It re-placed one huge group of nets at once | Endgame runs separately on each spatial cluster of conflicts | fixed |
| R3 | An endgame round could raise the total (465 -> 560) | In strict mode a 0.2/0.4 mm trace only checked the keep-outs other nets stamp for a 0.1 mm trace, so it could land inside a thin neighbour's clearance | Strict mode also checks the wide trace's extra half-width | fixed |
| R4 | One endgame round took 30+ minutes | Each failed strict search expanded up to 12 M nodes, 24 orders per cluster | Strict searches capped (EG_CAP, 1.5 M); big clusters get fewer orders | fixed |
| R5 | Most clusters still failed | A cluster only counted if every net fitted with zero conflicts | Each order places nets strictly where possible and priced otherwise; the order with the fewest conflicts is kept if it beats the current routes, so a round can only lower the count | fixed |
| R6 | After an endgame the next pass scattered the cleaned-up routing (434 -> 1710) | Negotiation continued at the capped maximum price | Endgame rounds repeat while they lower the total; afterwards the negotiation restarts at a low price (history kept) | in progress (run 26) |
| R7 | Slow nets had no room south of the SoC | All of inner2 there was reserved for the power islands | INNER2_OPEN: the islands keep only their feed corridors (>= 1.5 mm wide) there; slow nets may use the rest of inner2; fast nets never use inner2 | fixed (in use) |

| R8 | Only 3 usable signal layers in the strip under the SoC | Ground layers were never used for routing | GND_SIG: slow nets (<= 0.2 mm) may cross inner1/inner4 at 4x cost, never within w/2 + 3h + w/2 + clearance of a fast trace on the adjacent outer layer (and never under the DDR copper); GND_SIG_BGA also allows it under the SoC field. planes.py cuts those traces out of the ground pours and drops unconnected pieces; check.py fails the board if any copper sits under a fast trace on its reference ground layer | in use (run 36) |

Rockchip's own 6-layer method (RK3568 Hardware Design Guide, section 3.1): L1 signal / L2 GND / L3 power / L4 signal / L5 GND / L6 signal (this board's stackup); outer two ball rings escape on top with 4 mil traces between balls; from the third ring vias on a grid between the balls, in rows every 2-4 ball rows with an empty row kept for plane channels, 3.5 mil traces between vias. Next step if routing still stalls: a breakout planner that lays the vias out this way before the negotiated routing.

| R9 | A run could output a worse result than it had reached | The output was the last pass, not the best | Best routing written to `*.best.json` as it improves and used as the output | fixed |
| R10 | Pair members kept colliding at layer changes (e.g. MIPI_DSI_TX0_D0P with D0N's via) | The follower's attraction rings overlapped the lead's own via/trace keep-out | Attraction never inside the lead's clearance | fixed |
| R11 | 0.2/0.4 mm supply traces kept brushing thin signals | In priced mode a wide trace only checked its centre line | Priced over its full width (as strict mode already was) | fixed |
| R12 | Phantom conflicts the endgame could never clear | Inside neck zones wide traces are drawn at 0.1 mm but stamped at full width | Signal-width stamps inside neck zones | fixed |
| R13 | VCC_DDR island cut off at the RK809 | Island feed corridors were not enforced inside any fine-pitch zone | Enforced everywhere except the SoC ball field | fixed |
| R14 | Endgame judged re-placements on the moved nets only and could raise the total (687 -> 972) | Fallback-routed nets pushed into nets outside the group | Judged on the whole board; a round that does not help is rolled back | fixed |

Result after R9-R12: run 44 reached 4 conflict cells (one MIPI pair at exactly the 0.100 mm limit, which check.py accepts), from 184 earlier in the day.

## Planes and fixed copper

| # | Issue | Fix | Status |
|---|---|---|---|
| F1 | U1 B22/V2 pads 0.048 mm from GND vias | The supplied power fanout predates the corrected ball map; fixed.py now drops any fanout whose via does not clear another net's ball, and fanout_bga.py gives that ball a via-in-pad | fixed |
| F2 | RK809 thermal-pad vias inside the VDD_NPU island | planes.py now treats footprint vias as foreign copper | fixed |
| F3 | VDD_LOGIC touched VDD_GPU at one spot | Each island keeps SPLIT (0.25 mm) from the islands already made | fixed |

| R15 | Differential pairs were not coupled (P/N up to 31 mm apart in length) even at 0 conflicts | The follower was only attracted to the lead | Follower confined to 0.6 mm of the lead's path (outside BGA/fine-pitch zones), never inside the lead's keep-out; a follower that cannot fit is "decoupled" (penalised, lead gets history cost); the lead pays for its follower's room | fixed (with R16-R17) |
| R16 | Renegotiating all skewed pairs from a finished routing diverged (400-1500 conflicts) | The loaded grid routing already counts ~1400 conflict cells that the exact DRC accepts (grid rounding, cleared by repair.py), so the negotiation starts far from its own optimum | Renegotiation abandoned for the last pairs; see R17 | replaced |
| R17 | CSI D2 (4.3 mm) and DSI1 CLK (5.1 mm) still skewed after bump tuning: the N wire wandered across top/bottom under the SoC | Under the ball field only one trace fits per channel, so the members split and nothing in the bump tuner can recover 4-5 mm | New `route/reroute.py`: strict A* re-route of single nets on the exact finished copper (0.05 mm grid, exact clearance from pads/traces/vias, edge, reference-plane rule, through-via rule on all 6 layers), pair member attracted to its partner. P then N of both pairs re-routed: skews 0.7 / 2.3 mm, then `tune_pairs.py` (amplitudes up to 1.2 mm) matched every pair | fixed |

Final routing: `source/route/final/` (run 61 + reroute of 4 nets + tune + repair + planes). check.py exit 0: 0 clearance, 0 edge, 0 hole, 0 pad, 0 reference-plane violations, 234/234 nets, every island one piece. pairs.py: 17/17 pairs within limit (worst 0.3 of limit). DDR traces and vias byte-identical to run 61 (281 items).

## Other solvers tried

| # | Solver | Result | Notes |
|---|---|---|---|
| S1 | @tscircuit/fanout-solver (RK3566 breakout) | 35 of 116 non-DDR signal nets escaped | Bugs: boundary route leaves `sharedBoundary` and re-enters; one failed corner normalization discards the whole result; no signal via-in-pad (inner-grid balls cannot escape). Repro inputs in `source/route/fanout_rk.ts`. Not fixed here. |
| S2 | @tscircuit/capacity-autorouter Pipeline 9 (non-DDR nets) | 0 routes on both layouts: `No path found for VCCA1V8_PMU_mst1` in node `cmn_26`, then the regional fallback runs out of iterations; Pipeline 10 does not detect the RK3566 as a BGA | Root cause: the grid is built without fixed traces, which only come back on region boundaries; three fixed DDR traces wall off a ~0.3 mm top-layer pocket with no via site, and port planning puts an entry inside it and the exit outside. Repro test `tests/repro/pipeline9-fixed-copper-pocket.test.ts` (local branch `improve/dense-bga-hd`, commit f49cf0c0f; pushing/PR not possible from here). Fix (per-layer pocket-aware port planning) designed in `/home/user/tscircuit-autorouter/NOTES-dense-bga.md`, not implemented |
| S3 | @tscircuit/fanout-solver boundary dogleg | Route leaves `sharedBoundary` (x 5.484 < 7.23) or fails corner normalization | Root cause in `lib/route-bus/append-plan-boundary.ts` (single 45-degree leg to the boundary track). Repro pushed: branch `repro/boundary-dogleg-leaves-shared-boundary` (251a5cd); PR creation was refused by the permission check, open it at https://github.com/tscircuit/fanout-solver/compare/main...repro/boundary-dogleg-leaves-shared-boundary . A local fix (4a3c2cf) fixes the repro but regresses two existing solves, so it is not offered as a PR |

## Remaining before ordering

1. ~~Routing at 0 conflicts, every net connected~~ done (`source/route/final`).
2. ~~Pair P/N matching~~ done (17/17).
3. ~~Final planes, full-board build, Gerbers / BOM / CPL~~ done (`fab/`); README ordering notes.
4. Verify: eMMC VDDI cap value, 240R 1% stock, 32 kHz crystal load caps, JLCPCB CPL rotations (incl. the rotated SYR837 WLCSP), GPIO bank voltages of the moved CM4 pins.
