# Widens the traces of supply / switch-node nets in place (no re-route): every segment of such a net becomes its
# own trace, as wide as its target width (from the net's current, IPC-2221 10 C rise) or as wide as the copper
# around it allows (GAP to every other-net trace, via, pad and plane on that layer), whichever is smaller, in 0.02 mm
# steps. The centre line stays where it is, so connectivity and the rest of the board are unchanged.
# Usage: COPPER=final/copper.json ROUTES=final/routes.json python3 fatten_power.py   (rewrites both)
import json, os, math, collections
from shapely.geometry import Point, LineString, box, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree
D = os.path.dirname(os.path.abspath(__file__))
CP, RP = os.environ["COPPER"], os.environ["ROUTES"]
cu, rt = json.load(open(CP)), json.load(open(RP))
P = json.load(open(D + "/../design/pads.json")); pads, fvias = P["pads"], P["footprintVias"]
GAP, STEP = 0.1, 0.02
CUR = {"VCC5V0_SYS": 2.5, "VCC3V3_SYS": 2.0, "VCC_1V8": 0.8, "VCC_3V3": 0.6, "VCC3V3_PMU": 0.2, "VCCA_1V8": 0.3, "VCCA1V8_PMU": 0.2,
       "VDDA_0V9": 0.3, "VDDA0V9_PMU": 0.1, "VCCIO_SD": 0.3, "VCC3V3_SD": 0.5, "VCCIO6": 0.1, "VCCIO_ACODEC": 0.1, "VCCA1V8_IMAGE": 0.1,
       "VDDA0V9_IMAGE": 0.1, "SW1": 2.5, "SW2": 2.0, "SW3": 1.5, "SW4": 1.0, "SW5": 1.5, "SW_CPU": 3.0, "SW_3V3": 2.5}
def i_max(w, outer):
    a = w / 0.0254 * (1.378 if outer else 0.669)
    return (0.048 if outer else 0.024) * 10 ** 0.44 * a ** 0.725
def w_need(amps, outer):
    w = 0.1
    while i_max(w, outer) < amps and w < 3: w += 0.02
    return round(w, 2)
padg = lambda p: Point(p["x"], p["y"]).buffer(p["w"] / 2, 16) if p["shape"] == "circle" else box(p["x"] - p["w"] / 2, p["y"] - p["h"] / 2, p["x"] + p["w"] / 2, p["y"] + p["h"] / 2)
plane_geo = []
if os.environ.get("PLANES") and os.path.exists(os.environ["PLANES"]):
    for q in json.load(open(os.environ["PLANES"])):
        plane_geo.append((q["layer"], q["net"], Polygon([(a["x"], a["y"]) for a in q["outer"]], [[(a["x"], a["y"]) for a in h] for h in q["holes"]]).buffer(0)))
def obstacles(layer, net):
    g = [padg(p) for p in pads if p["layer"] == layer and p["net"] != net]
    g += [LineString([(q["x"], q["y"]) for q in t["pts"]]).buffer(t["w"] / 2) for t in cu["traces"] if t["layer"] == layer and t["net"] != net and len(t["pts"]) > 1]
    g += [Point(v["x"], v["y"]).buffer(v["d"] / 2) for v in cu["vias"] + [dict(v, net="GND") for v in fvias] if v["net"] != net]
    return STRtree(g), g
new, changed, report = [], 0, collections.defaultdict(list)
cache = {}
for t in cu["traces"]:
    n = t["net"]
    if n not in CUR or len(t["pts"]) < 2: new.append(t); continue
    outer = t["layer"] in ("top", "bottom"); target = w_need(CUR[n], outer)
    if t["w"] >= target: new.append(t); continue
    if (t["layer"], n) not in cache: cache[(t["layer"], n)] = obstacles(t["layer"], n)
    tree, gs = cache[(t["layer"], n)]
    for a, b in zip(t["pts"], t["pts"][1:]):
        seg = LineString([(a["x"], a["y"]), (b["x"], b["y"])])
        if seg.length < 1e-6: continue
        near = [gs[i] for i in tree.query(seg.buffer(target / 2 + GAP + 0.01))]
        u = unary_union(near) if near else None
        w = t["w"]
        while w + STEP <= target + 1e-9:
            if u is not None and seg.buffer((w + STEP) / 2, cap_style=1).distance(u) < GAP - 1e-6: break
            w = round(w + STEP, 3)
        new.append({"pts": [dict(a), dict(b)], "layer": t["layer"], "w": w, "net": n})
        if w > t["w"]: changed += 1
        report[n].append((round(seg.length, 2), w, target, t["layer"]))
cu["traces"] = new
for n in rt["nets"]:
    if n in CUR: rt["nets"][n]["segs"] = [dict(t) for t in cu["traces"] if t["net"] == n]
json.dump(cu, open(CP, "w")); json.dump(rt, open(RP, "w"))
print(f"widened {changed} segments")
for n, segs in report.items():
    short = [s for s in segs if s[1] < s[2]]
    worst = max((s for s in short), key=lambda s: s[0], default=None)
    print(f"{n:14s} target {segs[0][2]} mm outer / {w_need(CUR[n], False)} inner: {len(short)} of {len(segs)} segments still narrower; longest such {worst}")
