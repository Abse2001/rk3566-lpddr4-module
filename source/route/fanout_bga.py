# Via-in-pad for the supply and ground balls of the RK3566 inner 0.65 mm grid and of the eMMC (0.5 mm), where
# the supplied DDR-corner fanout has not already dropped the ball. A via goes on the ball centre when it clears
# all other copper by 0.1 mm on every layer; the decoupling capacitors under the SoC (place.py) sit on these vias.
# Output: bga_vias.json [{x, y, d, hole, net, ball}]
import json, os, math
from shapely.geometry import Point, LineString, box
from shapely.strtree import STRtree
D = os.path.dirname(os.path.abspath(__file__))
net = json.load(open(D + "/../design/netlist.json"))
pins = {c["ref"]: c["pins"] for c in net["components"]}
pads = json.load(open(D + "/../design/pads.json"))["pads"]
fixed = json.load(open(D + "/fixed.json"))
VIA_D, VIA_H, GAP = 0.25, 0.15, 0.1
RAILS = ("GND", "VDD_", "VCC", "VDDA")
copper = []  # (geom, net)
for t in fixed["traces"]:
    for a, b in zip(t["pts"], t["pts"][1:]):
        copper.append((LineString([(a["x"], a["y"]), (b["x"], b["y"])]).buffer(t["w"] / 2), t["net"]))
for v in fixed["vias"]:
    copper.append((Point(v["x"], v["y"]).buffer(v["d"] / 2), v["net"]))
for p in pads:
    g = Point(p["x"], p["y"]).buffer(p["w"] / 2) if p["shape"] == "circle" else box(p["x"] - p["w"] / 2, p["y"] - p["h"] / 2, p["x"] + p["w"] / 2, p["y"] + p["h"] / 2)
    copper.append((g, p["net"]))
NFIXED = sum(len(t["pts"]) - 1 for t in fixed["traces"]) + len(fixed["vias"])
tree = STRtree([g for g, _ in copper])
out = []
for p in pads:
    if p["ref"] not in ("U1", "U6") or not p["net"]: continue
    n = p["net"]
    if not (n == "GND" or n.startswith(("VDD", "VCC"))): continue
    ball = p["names"][0]
    if p["ref"] == "U1" and not ball.startswith("1"): continue  # perimeter 0.4 mm band: fanned out by the router
    via = Point(p["x"], p["y"]).buffer(VIA_D / 2)
    # already dropped by the supplied fanout: a same-net fixed via or trace touches the pad
    pad_g = Point(p["x"], p["y"]).buffer(p["w"] / 2 + 0.01)
    if any(copper[k][1] == n and copper[k][0].intersects(pad_g) for k in tree.query(pad_g) if k < NFIXED):
        continue
    ok = True
    for k in tree.query(via.buffer(GAP)):
        g, kn = copper[k]
        if kn == n: continue
        if g.distance(via) < GAP - 1e-6: ok = False; break
    for q in out:  # vias placed so far: hole and pad spacing
        if math.hypot(q["x"] - p["x"], q["y"] - p["y"]) < VIA_D + GAP - 1e-6: ok = False; break
    if ok:
        out.append({"x": p["x"], "y": p["y"], "d": VIA_D, "hole": VIA_H, "net": n, "ball": f"{p['ref']}.{ball}"})
json.dump(out, open(D + "/bga_vias.json", "w"))
from collections import Counter
print("via-in-pad", len(out), Counter(v["net"] for v in out).most_common(20))
