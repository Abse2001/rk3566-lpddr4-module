#!/bin/bash
# Finishing chain for a solved (ECO) routing run:
#   merge kept + re-routed routes -> tune pairs -> strict re-route of pairs still skewed (both orders, via costs and
#   search margins; an attempt where a net fails is discarded) -> tune -> repair -> planes -> join orphan rail vias
#   to their island (MODE=island) -> planes -> check.py and pairs.py.
# Usage: finish_eco.sh <run tag, e.g. _l11> <frozen.json> <out dir>
set -e
TAG=$1; FZ=$2; F=$3
R=$(cd "$(dirname "$0")" && pwd); SRC=$R/..
mkdir -p $F
cp $R/copper$TAG.json $F/copper.json
python3 - "$R/routes$TAG.json" "$R/final/routes.json" "$FZ" "$F/routes.json" <<'EOF'
import json, sys
new = json.load(open(sys.argv[1])); old = json.load(open(sys.argv[2]))["nets"]; fz = json.load(open(sys.argv[3]))
keep = {t["net"] for t in fz["traces"]} | {v["net"] for v in fz["vias"]}
nets = dict(new["nets"])
for n in keep:
    if n in old and n not in nets: nets[n] = old[n]
json.dump(dict(new, nets=nets), open(sys.argv[4], "w"))
EOF
cd $SRC
TUNE="AMPS=1.2,0.9,0.7,0.55,0.45,0.35,0.25,0.15,0.1,0.07 MIN_L=0.25"
env $TUNE ROUTES=$F/routes.json COPPER=$F/copper.json python3 route/tune_pairs.py > /dev/null
for line in $(python3 pairs.py $F/routes.json | grep "TOO" | awk '{print $1","$4}'); do
  P=${line%,*}; N=${line#*,}; best=99
  cp $F/routes.json $F/r.base; cp $F/copper.json $F/c.base
  for ord in "$P,$N" "$N,$P"; do for vc in 0.6 2 4; do for mb in 4 6; do
    cp $F/r.base $F/r.try; cp $F/c.base $F/c.try
    out=$(MARGIN_BOX=$mb M=0.004 VIA_COST=$vc ROUTES=$F/r.try COPPER=$F/c.try NETS=$ord python3 route/reroute.py 2>&1)
    echo "$out" | grep -q FAILED && continue
    env $TUNE ROUTES=$F/r.try COPPER=$F/c.try python3 route/tune_pairs.py > /dev/null 2>&1
    sk=$(python3 pairs.py $F/r.try | grep "^$P " | awk '{print $8}'); [ -z "$sk" ] && continue
    if python3 -c "import sys; sys.exit(0 if $sk < $best else 1)"; then best=$sk; cp $F/r.try $F/r.best; cp $F/c.try $F/c.best; fi
  done; done; done
  if [ "$best" != "99" ]; then cp $F/r.best $F/routes.json; cp $F/c.best $F/copper.json; fi
  echo "pair $P: best skew after re-route $best"
done
COPPER=$F/copper.json python3 route/repair.py | tail -1
COPPER=$F/copper.json PLANES_OUT=$F/planes.json python3 route/planes.py > /dev/null 2>&1
MODE=island JOIN_R=3 COPPER=$F/copper.json PLANES=$F/planes.json python3 route/join_orphans.py
COPPER=$F/copper.json PLANES_OUT=$F/planes.json python3 route/planes.py 2>&1 | grep -E "^VDD|^VCC"
python3 pairs.py $F/routes.json | grep -E "TOO|worst"
COPPER=$F/copper.json PLANES=$F/planes.json python3 check.py 2>&1 | grep -v "^Via hole" | head -20 || true
