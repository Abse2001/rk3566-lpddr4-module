#!/bin/bash
# Rebuilds the RK3566 module from the design data to fabrication files.
#   design/netlist.py      netlist (RK3566 ball map, CM4 pin map, power tree)
#   design/place.py        placement (decaps under the SoC on the ball vias)
#   build.tsx MODE=pads    exact pads with nets
#   route/fixed.py         the routed LPDDR4 block and the supplied power fanout, in board coordinates
#   route/fanout_bga.py    via-in-pad on the SoC/eMMC supply and ground balls
#   route/route.ts         plane drops first (PLANES_ONLY), then island corridors (planes.py), then everything
#   route/tune_pairs.py    P/N length matching of the differential pairs
#   route/planes.py        ground planes and supply islands
#   build.tsx              index.circuit.json;  check.py: whole-board DRC + connectivity;  export.ts: fab/
set -e
cd "$(dirname "$0")"
python3 design/netlist.py
python3 route/fixed.py
python3 design/place.py
MODE=pads bun build.tsx
python3 route/fanout_bga.py
(cd route && rm -f corridors.json && PLANES_ONLY=1 MAXIT=40 bun route.ts | tail -1)
(cd route && CORRIDORS_OUT=corridors.json python3 planes.py | tail -6)
(cd route && MAXIT=${MAXIT:-300} bun route.ts | tail -3)
python3 route/tune_pairs.py | tail -25
python3 route/planes.py | tail -6
bun build.tsx
python3 pairs.py route/routes.json | tail -3
python3 check.py
bun export.ts
