# Research outputs

| File | What |
|---|---|
| `ddr-delay-check.txt` | Delay-based LPDDR4 check of the final DDR block (`source/route/ddr_timing.py`): per-layer ps/mm from the JLC06161H-1080A stackup plus via barrels. All groups pass; CK/DQS P/N 0.0–0.1 ps. |
| `ddr-delay-check-published-v18.txt` | The same check on the previously published DDR block. CK_a 50–63 ps and DQS1 ~18 ps P/N skew, which length-only checks missed. |
| `ngspice-ddr-v20.txt` | ngspice channel simulation (`ddr_sim.py`, generic 40 Ω / 60 Ω ODT I/O, 1560 MT/s) of the delay-aware DDR block: DQ eyes 660 mV / 538 of 641 ps, CK crossing skew 0.0 ps (67.6 ps before). |
| `solver-run-v*.log` | NegotiatedLaneSolver runs. v18 is the published block; v20/v21 are delay-aware; v22 is the final block, solved against the current power fanout. |
| `eco-route-l11.log` | The ECO board routing that reached 0 conflicts in 7 minutes. |
| `ddr.lane.routed.orig.json` | The originally published DDR block, kept for comparison. |

See also `../JLC-RULES.md`, `../ROUTING-PLAYBOOK.md`, `../ISSUES-AND-FIXES.md` and `../solver-patches/`.
