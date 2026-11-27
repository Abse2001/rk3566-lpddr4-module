# Releases kept signal nets near the conflict spots of a previous ECO run (GROW=routes_x.best.json, GROW_R mm):
# frozen copper = COPPER minus the RIP nets minus those nets. DDR_*, plane nets and fixed copper never move.
import json, os, sys
from shapely.geometry import Point, LineString
from shapely.ops import unary_union
S = os.path.dirname(os.path.abspath(__file__)) + "/.."
cu = json.load(open(os.environ["COPPER"])); rip = set(json.load(open(os.environ["RIP"])))
PLANE = {"GND", "VDD_CPU", "VDD_LOGIC", "VDD_GPU", "VDD_NPU", "VCC_DDR", "VCC0V6_DDR"}
fx = json.load(open(S + "/route/fixed.json")); fixed_nets = {t["net"] for t in fx["traces"]} | {v["net"] for v in fx["vias"]}
R = float(os.environ.get("GROW_R", 0.8))
spots = json.load(open(os.environ["GROW"])).get("spots", [])
hot = unary_union([Point(s[0], s[1]).buffer(R) for s in spots])
free = lambda n: n and n not in PLANE and not n.startswith("DDR_") and n not in fixed_nets
grow = {t["net"] for t in cu["traces"] if free(t["net"]) and t["net"] not in rip and len(t["pts"]) > 1 and LineString([(q["x"], q["y"]) for q in t["pts"]]).intersects(hot)}
grow |= {v["net"] for v in cu["vias"] if free(v["net"]) and v["net"] not in rip and hot.contains(Point(v["x"], v["y"]))}
# pairs move together
import re
names = {t["net"] for t in cu["traces"]}
for n in list(grow):
    m = re.match(r"(.*?)(P|N|_P|_N|DP|DM)(_C)?$", n)
    if m:
        sw = {"P": "N", "N": "P", "_P": "_N", "_N": "_P", "DP": "DM", "DM": "DP"}[m.group(2)]
        q = m.group(1) + sw + (m.group(3) or "")
        if q in names: grow.add(q)
allrip = rip | grow
json.dump({"traces": [t for t in cu["traces"] if t["net"] not in allrip], "vias": [v for v in cu["vias"] if v["net"] not in allrip]}, open(os.environ["FROZEN"], "w"))
json.dump(sorted(allrip), open(os.environ["RIP_OUT"], "w"))
print(f"{len(spots)} spots, released {len(grow)} more nets: {sorted(grow)}")
