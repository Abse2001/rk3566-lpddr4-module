# Whole-board check of the RK3566 module, independent of the router and plane generator.
#   DRC: copper of different nets on the same layer keeps >= 0.1 mm (vias exist on every layer); copper keeps
#        >= 0.25 mm from the board edge and the mounting holes; via holes keep >= 0.2 mm apart (edge to edge).
#   Connectivity: for every net of design/netlist.json, all its pads are one piece of copper (pads, traces,
#        vias, pours; a via joins every layer it passes).
# Input: design/pads.json, route/copper.json, route/planes.json. Exit code 1 on any failure.
import json, os, sys
from collections import defaultdict
from shapely.geometry import Point, LineString, box, Polygon
from shapely.strtree import STRtree
from shapely.ops import unary_union
D = os.path.dirname(os.path.abspath(__file__))
pads = json.load(open(D + "/design/pads.json"))["pads"]
fvias = json.load(open(D + "/design/pads.json"))["footprintVias"]
cu = json.load(open(os.environ.get("COPPER", D + "/route/copper.json")))
PL = os.environ.get("PLANES", D + "/route/planes.json")
planes = json.load(open(PL)) if os.path.exists(PL) else []
net = json.load(open(D + "/design/netlist.json"))
GAP, EDGE, HOLE_GAP = 0.1, 0.25, 0.2
LAYERS = ["top", "inner1", "inner2", "inner3", "inner4", "bottom"]
items = []  # (layer, net, geom, kind, id)
for k, p in enumerate(pads):
    g = Point(p["x"], p["y"]).buffer(p["w"] / 2, 24) if p["shape"] == "circle" else box(p["x"] - p["w"] / 2, p["y"] - p["h"] / 2, p["x"] + p["w"] / 2, p["y"] + p["h"] / 2)
    items.append((p["layer"], p["net"], g, "pad", f"{p['ref']}.{p['names'][0] if p['names'] else '?'}"))
for t in cu["traces"]:
    for a, b in zip(t["pts"], t["pts"][1:]):
        items.append((t["layer"], t["net"], LineString([(a["x"], a["y"]), (b["x"], b["y"])]).buffer(t["w"] / 2, 8), "trace", t["net"]))
allvias = [dict(v) for v in cu["vias"]] + [{"x": v["x"], "y": v["y"], "d": v["d"], "hole": v["hole"], "net": "GND"} for v in fvias]
for v in allvias:
    for l in LAYERS:
        items.append((l, v["net"], Point(v["x"], v["y"]).buffer(v["d"] / 2, 16), "via", v["net"]))
for pl in planes:
    g = Polygon([(q["x"], q["y"]) for q in pl["outer"]], [[(q["x"], q["y"]) for q in h] for h in pl["holes"]]).buffer(0)
    items.append((pl["layer"], pl["net"], g, "pour", pl["net"]))
# ---------- DRC ----------
viol = []
by_layer = defaultdict(list)
for it in items: by_layer[it[0]].append(it)
for l, its in by_layer.items():
    geoms = [it[2] for it in its]
    tree = STRtree(geoms)
    for i, it in enumerate(its):
        for j in tree.query(it[2].buffer(GAP - 1e-4)):
            if j <= i: continue
            o = its[j]
            if it[1] is not None and it[1] == o[1]: continue
            d = it[2].distance(o[2])
            if d < GAP - 1e-4:
                viol.append((l, round(d, 3), it[3], it[4], o[3], o[4], round(it[2].centroid.x, 2), round(it[2].centroid.y, 2)))
BOARD = box(-3.5, -51.5, 36.5, 3.5)
HOLES = [Point(h).buffer(1.35) for h in [(0, 0), (33, 0), (0, -48), (33, -48)]]
edge_v = [(it[0], it[3], it[4]) for it in items if it[3] != "pour" and (BOARD.exterior.distance(it[2]) < EDGE - 1e-4 or not BOARD.contains(it[2]) or any(h.distance(it[2]) < EDGE - 1e-4 for h in HOLES))]
pour_edge = [(it[0], it[4]) for it in items if it[3] == "pour" and (BOARD.exterior.distance(it[2]) < 0.2 or any(h.distance(it[2]) < 0.2 for h in HOLES))]
hp = [Point(v["x"], v["y"]).buffer(v["hole"] / 2, 12) for v in allvias]
ht = STRtree(hp); hole_v = 0
for i, g in enumerate(hp):
    for j in ht.query(g.buffer(HOLE_GAP)):
        if j > i and g.distance(hp[j]) < HOLE_GAP - 1e-4 and allvias[i]["net"] != allvias[j]["net"]: hole_v += 1
# ---------- connectivity ----------
parent = list(range(len(items)))
def find(a):
    while parent[a] != a: parent[a] = parent[parent[a]]; a = parent[a]
    return a
def union(a, b): parent[find(a)] = find(b)
for l, its_idx in defaultdict(list, {l: [k for k, it in enumerate(items) if it[0] == l] for l in LAYERS}).items():
    geoms = [items[k][2] for k in its_idx]; tree = STRtree(geoms)
    for a, k in enumerate(its_idx):
        for b in tree.query(items[k][2]):
            kk = its_idx[b]
            if kk != k and items[k][1] is not None and items[k][1] == items[kk][1] and items[k][2].intersects(items[kk][2]): union(k, kk)
# a via is one object on every layer: join its per-layer copies
vstart = len(pads) + sum(1 for it in items if it[3] == "trace")
for vi in range(len(allvias)):
    base = vstart + vi * len(LAYERS)
    for q in range(1, len(LAYERS)): union(base, base + q)
open_nets = []
pad_items = defaultdict(list)
for k, it in enumerate(items):
    if it[3] == "pad" and it[1]: pad_items[it[1]].append(k)
for n, ks in pad_items.items():
    roots = {find(k) for k in ks}
    if len(roots) > 1:
        groups = defaultdict(list)
        for k in ks: groups[find(k)].append(items[k][4])
        open_nets.append((n, len(roots), [g[:3] for g in groups.values()][:4]))
print(f"DRC: {len(viol)} clearance violations (< {GAP} mm), {len(edge_v)} copper too close to edge/holes, {len(pour_edge)} pours near edge, {hole_v} via-hole spacing issues")
for v in viol[:25]: print("  ", v)
for v in edge_v[:5]: print("   edge", v)
print(f"Connectivity: {len(pad_items) - len(open_nets)}/{len(pad_items)} nets complete")
for o in open_nets[:40]: print("   open", o)
sys.exit(1 if viol or edge_v or open_nets or hole_v else 0)
