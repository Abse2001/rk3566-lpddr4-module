# ECO (engineering change) on a finished routing: keep the copper of every net the change does not touch, re-route
# only the rest. A net is re-routed when
#   - any of its pads moved (or its part changed side or rotation), or a pad no longer meets its old copper,
#   - any of its old copper comes within GAP of the new fixed copper (DDR block, power fanout, via-in-pad, escape
#     stubs) or of a pad of another net in the new placement,
#   - it is the partner of a re-routed differential pair member (pairs are routed together).
# Input: OLD_ROUTES / OLD_COPPER (the finished routing), OLD_PADS (its pads.json), the current design/pads.json,
#        fixed.json + bga_vias.json. Output: FROZEN (copper of the kept nets, fixed copper for route.ts FROZEN=) and
#        the list of re-routed nets.
import json, os, re
from shapely.geometry import Point, LineString, box
from shapely.strtree import STRtree
D = os.path.dirname(os.path.abspath(__file__))
oc = json.load(open(os.environ["OLD_COPPER"])); orr = json.load(open(os.environ["OLD_ROUTES"]))["nets"]
key = lambda p: (p["ref"], p["names"][0] if p["names"] else f"{p['x']:.3f},{p['y']:.3f}")
op = {key(p): p for p in json.load(open(os.environ["OLD_PADS"]))["pads"]}
NP = json.load(open(D + "/../design/pads.json")); npads = NP["pads"]
fx = json.load(open(D + "/fixed.json")); bv = json.load(open(D + "/bga_vias.json"))
GAP = 0.1
L = ["top", "inner1", "inner2", "inner3", "inner4", "bottom"]
padg = lambda p: Point(p["x"], p["y"]).buffer(p["w"] / 2, 16) if p["shape"] == "circle" else box(p["x"] - p["w"] / 2, p["y"] - p["h"] / 2, p["x"] + p["w"] / 2, p["y"] + p["h"] / 2)
fixed_nets = {t["net"] for t in fx["traces"]} | {v["net"] for v in fx["vias"]}
rip, why = set(), {}
# plane nets (ground and the inner2 islands) are many independent pad-to-via drops: keep each drop that is still
# valid and drop only the pieces at moved pads or in conflict; route.ts then routes just their open pads
PLANE = {"GND", "VDD_CPU", "VDD_LOGIC", "VDD_GPU", "VDD_NPU", "VCC_DDR"}
drop_piece = set()  # ("t", index) / ("v", index) of plane-net copper to remove
def mark(n, r):
    if n in PLANE: return
    if n and n not in rip: rip.add(n); why[n] = r
moved_old = []  # old pad shapes of moved pads (plane-net drops that ended on them are removed)
# 1. moved pads
for p in npads:
    o = op.get(key(p))
    if o is None or abs(o["x"] - p["x"]) > 1e-4 or abs(o["y"] - p["y"]) > 1e-4 or o["layer"] != p["layer"] or o["net"] != p["net"]:
        mark(p["net"], f"pad {key(p)} moved")
        if o is not None and p["net"] in PLANE: moved_old.append((o["layer"], padg(o).buffer(0.01), p["net"]))
# 2. old copper of a routed net vs the new fixed copper and new pads (all other nets)
obs = {l: [] for l in L}
for t in fx["traces"]:
    obs[t["layer"]].append((LineString([(q["x"], q["y"]) for q in t["pts"]]).buffer(t["w"] / 2), t["net"]))
for v in fx["vias"] + bv + [dict(v, net="GND") for v in NP["footprintVias"]]:
    for l in L: obs[l].append((Point(v["x"], v["y"]).buffer(v["d"] / 2), v["net"]))
for p in npads: obs[p["layer"]].append((padg(p), p["net"]))
trees = {l: STRtree([g for g, _ in obs[l]]) for l in L}
routed = {t["net"] for t in oc["traces"]} | {v["net"] for v in oc["vias"]}
routed -= fixed_nets - set(orr)  # DDR / fixed nets are not part of the old routing's own copper
def hits(g, layers, net):
    for l in layers:
        for j in trees[l].query(g.buffer(GAP)):
            og, on = obs[l][j]
            if on != net and og.distance(g) < GAP - 1e-4: return f"{l} near {on}"
    return None
for k, t in enumerate(oc["traces"]):
    n = t["net"]
    if n not in orr or n in rip: continue
    g = LineString([(q["x"], q["y"]) for q in t["pts"]]).buffer(t["w"] / 2)
    h = hits(g, [t["layer"]], n)
    if n in PLANE:
        if h or any(l == t["layer"] and pn == n and g.intersects(pg) for l, pg, pn in moved_old): drop_piece.add(("t", k))
    elif h: mark(n, "trace " + h)
for k, v in enumerate(oc["vias"]):
    n = v["net"]
    if n not in orr or n in rip: continue
    g = Point(v["x"], v["y"]).buffer(v["d"] / 2)
    h = hits(g, L, n)
    if n in PLANE:
        if h or any(pn == n and g.intersects(pg) for l, pg, pn in moved_old): drop_piece.add(("v", k))
    elif h: mark(n, "via " + h)
# 2b. grow the change region: kept nets whose copper lies within GROW_R of the conflict spots a previous ECO run
#     could not clear (GROW=routes_xxx.best.json) are re-routed too, so they can negotiate with the changed nets
if os.environ.get("GROW"):
    R = float(os.environ.get("GROW_R", 0.8))
    spots = json.load(open(os.environ["GROW"])).get("spots", [])
    from shapely.ops import unary_union
    hot = unary_union([Point(sx, sy).buffer(R) for sx, sy, *_ in spots]) if spots else None
    if hot is not None:
        for t in oc["traces"]:
            if t["net"] in orr and t["net"] not in PLANE and t["net"] not in rip and LineString([(q["x"], q["y"]) for q in t["pts"]]).intersects(hot):
                mark(t["net"], "near an unresolved conflict")
        for v in oc["vias"]:
            if v["net"] in orr and v["net"] not in PLANE and v["net"] not in rip and hot.contains(Point(v["x"], v["y"])):
                mark(v["net"], "near an unresolved conflict")
# 3. pairs together
def partner(n):
    for a, b in (("P", "N"), ("N", "P"), ("DP", "DM"), ("DM", "DP")):
        m = re.match(rf"(.*){a}(_C)?$", n)
        if m and (m.group(1) + b + (m.group(2) or "")) in orr: return m.group(1) + b + (m.group(2) or "")
for n in list(rip):
    q = partner(n)
    if q: mark(q, f"partner of {n}")
keep = [n for n in orr if n not in rip]
frozen = {"traces": [t for k, t in enumerate(oc["traces"]) if t["net"] in keep and ("t", k) not in drop_piece],
          "vias": [v for k, v in enumerate(oc["vias"]) if v["net"] in keep and ("v", k) not in drop_piece]}
json.dump(frozen, open(os.environ["FROZEN"], "w"))
print(f"{len(orr)} routed nets: keep {len(keep)} (plane nets partly: {len(drop_piece)} drop pieces removed), re-route {len(rip & set(orr))}")
for n in sorted(rip & set(orr)): print("  ", n, "-", why[n])
