# JLCPCB via-hole rule on the routed LPDDR4 block: a drilled via hole keeps 0.2 mm from copper of other nets on
# every layer. The block was routed with a 0.1 mm copper gap, so a 0.11 mm trace passing a 0.15/0.25 mm via can be
# up to 0.05 mm short. Each such DDR trace is fixed locally, in this order:
#   1. neck-down: the trace narrows to 0.09 mm (JLCPCB's minimum, allowed in BGA fan-outs) over the stretch next to
#      the via,
#   2. a small detour: a 45-degree trapezoid that steps the trace away from the via by the remaining shortfall.
# A change is kept only if the trace then clears all other copper by 0.1 mm and every other-net via hole by 0.2 mm.
# Input/output: ddr.lane.routed.json (RK3566-local coordinates, rewritten in place; the original is kept as
# ddr.lane.routed.orig.json). Obstacles: fixed.json (power fanout), bga_vias.json, footprint vias, pads.json.
# Run fixed.py afterwards, then rk-check.ts for the Rockchip timing rules.
import json, os, math, shutil
from shapely.geometry import Point, LineString, box
from shapely.strtree import STRtree
D = os.path.dirname(os.path.abspath(__file__))
RK = (15.2, -19.0)
SRC = D + "/ddr.lane.routed.json"
if not os.path.exists(D + "/ddr.lane.routed.orig.json"): shutil.copy(SRC, D + "/ddr.lane.routed.orig.json")
R = json.load(open(SRC))
fx = json.load(open(D + "/fixed.json")); bv = json.load(open(D + "/bga_vias.json")); P = json.load(open(D + "/../design/pads.json"))
GAP, HOLE, WMIN, EPS = 0.1, 0.2, 0.09, 1e-4
LAY = ["top", "inner1", "inner2", "inner3", "inner4", "bottom"]
loc = lambda x, y: (x - RK[0], y - RK[1])
# ---- static obstacles (local coordinates): pads, power fanout traces, every non-DDR via ----
stat = {l: [] for l in LAY}       # (geom, net)
vias = []                         # (x, y, d, hole, net)
for p in P["pads"]:
    x, y = loc(p["x"], p["y"])
    g = Point(x, y).buffer(p["w"] / 2, 16) if p["shape"] == "circle" else box(x - p["w"] / 2, y - p["h"] / 2, x + p["w"] / 2, y + p["h"] / 2)
    stat[p["layer"]].append((g, p["net"]))
for t in fx["traces"]:
    if t["net"].startswith("DDR_"): continue
    if t["layer"] in stat: stat[t["layer"]].append((LineString([loc(q["x"], q["y"]) for q in t["pts"]]).buffer(t["w"] / 2, 8), t["net"]))
for v in [v for v in fx["vias"] if not v["net"].startswith("DDR_")] + bv + [dict(v, net="GND") for v in P["footprintVias"]]:
    vias.append((*loc(v["x"], v["y"]), v["d"], v["hole"], v["net"]))
# ---- DDR traces as editable segment lists ----
traces = [t for t in R["traces"] if not t["connection_name"].startswith("power_")]
net_of = lambda t: "DDR_" + t["connection_name"]
for t in traces:
    for p in t["route"]:
        if p["route_type"] == "via": vias.append((p["x"], p["y"], p.get("via_diameter", 0.25), p.get("via_hole_diameter", 0.15), net_of(t)))
def segs(t):
    """(layer, width, LineString) of every wire segment of a DDR trace"""
    r = t["route"]; out = []
    for a, b in zip(r, r[1:]):
        if a["route_type"] == "wire" and b["route_type"] == "wire" and a["layer"] == b["layer"]:
            out.append((a["layer"], a["width"], LineString([(a["x"], a["y"]), (b["x"], b["y"])])))
    return out
# spatial indexes: via holes (static), and per layer all copper (static + DDR traces, rebuilt when a trace changes)
HOLES_G = [Point(x, y).buffer(h / 2, 12) for x, y, d, h, vn in vias]
HOLE_TREE = STRtree(HOLES_G)
ddr_cu = {}  # k -> [(layer, geom)]
def ddr_geoms(k):
    return [(l, ls.buffer(w / 2, 8)) for l, w, ls in segs(traces[k]) if ls.length > 0]
for k in range(len(traces)): ddr_cu[k] = ddr_geoms(k)
TREES = {}
def rebuild():
    for l in LAY:
        items = [(g, n, None) for g, n in stat[l]] + [(g, net_of(traces[k]), k) for k in ddr_cu for ll, g in ddr_cu[k] if ll == l]
        TREES[l] = (STRtree([i[0] for i in items]), items)
rebuild()
def geoms_except(k): return k
def problems(k, others=None):
    """violations of trace k: (kind, layer, need, via or None, segment index)"""
    t = traces[k]; n = net_of(t); out = []
    r = t["route"]
    for i, (a, b) in enumerate(zip(r, r[1:])):
        if not (a["route_type"] == "wire" and b["route_type"] == "wire" and a["layer"] == b["layer"]): continue
        ls = LineString([(a["x"], a["y"]), (b["x"], b["y"])])
        if ls.length == 0: continue
        g = ls.buffer(a["width"] / 2, 8); l = a["layer"]
        for j in HOLE_TREE.query(g.buffer(HOLE)):
            x, y, d, h, vn = vias[j]
            if vn == n: continue
            dd = HOLES_G[j].distance(g)
            if dd < HOLE - EPS: out.append(("hole", l, HOLE - dd, (x, y), i))
        tree, items = TREES[l]
        for j in tree.query(g.buffer(GAP)):
            og, on, owner = items[j]
            if owner == k or on == n: continue
            dd = og.distance(g)
            if dd < GAP - EPS: out.append(("gap", l, GAP - dd, None, i))
    return out
def neck(t, i, v, reach=0.45):
    """split segment i so the part within reach of v is its own segment, and narrow that part to WMIN"""
    r = t["route"]; a, b = r[i], r[i + 1]
    ls = LineString([(a["x"], a["y"]), (b["x"], b["y"])]); L = ls.length
    s = ls.project(Point(v)); s0, s1 = max(0, s - reach), min(L, s + reach)
    pts = []
    for q in (s0, s1):
        if 1e-6 < q < L - 1e-6:
            pp = ls.interpolate(q); pts.append((q, pp.x, pp.y))
    new = [dict(a)]
    for q, x, y in pts: new.append(dict(a, x=round(x, 5), y=round(y, 5)))
    # widths: the point that starts the stretch [s0, s1] gets WMIN
    for k, (q, x, y) in enumerate(pts):
        if abs(q - s0) < 1e-9: new[k + 1]["width"] = WMIN
        if abs(q - s1) < 1e-9: new[k + 1]["width"] = a["width"]
    if s0 <= 1e-6: new[0]["width"] = WMIN
    t["route"] = r[:i] + new + r[i + 1:]
def neck_all(t, l, v, reach=0.45):
    """narrow every segment of t on layer l that passes within reach of v (around corners too)"""
    for _ in range(12):
        r = t["route"]; hit = None
        for j, (a, b) in enumerate(zip(r, r[1:])):
            if a["route_type"] == b["route_type"] == "wire" and a["layer"] == b["layer"] == l and a["width"] > WMIN:
                ls = LineString([(a["x"], a["y"]), (b["x"], b["y"])])
                if ls.length > 1e-6 and ls.distance(Point(v)) < reach - 1e-6:
                    # the part within reach, unless already narrow
                    hit = j; break
        if hit is None: return
        neck(t, hit, v, reach)
def corner(t, l, v, shift):
    """move the trace's vertex nearest to v (an interior vertex on layer l) away from v by shift"""
    r = t["route"]; best = None
    for j in range(1, len(r) - 1):
        p, a, b = r[j], r[j - 1], r[j + 1]
        if p["route_type"] == a["route_type"] == b["route_type"] == "wire" and p["layer"] == a["layer"] == b["layer"] == l:
            d = math.hypot(p["x"] - v[0], p["y"] - v[1])
            if best is None or d < best[0]: best = (d, j)
    if not best or best[0] < 1e-6: return False
    d, j = best; p = r[j]
    p["x"] = round(p["x"] + (p["x"] - v[0]) / d * shift, 5); p["y"] = round(p["y"] + (p["y"] - v[1]) / d * shift, 5)
    return True
def shift_seg(t, l, v, shift):
    """move the whole segment nearest to v (both ends interior wire vertices) straight away from v"""
    r = t["route"]; best = None
    for j in range(1, len(r) - 2):
        a, b = r[j], r[j + 1]
        if not (a["route_type"] == b["route_type"] == r[j - 1]["route_type"] == r[j + 2]["route_type"] == "wire"): continue
        if not (a["layer"] == b["layer"] == r[j - 1]["layer"] == r[j + 2]["layer"] == l): continue
        ls = LineString([(a["x"], a["y"]), (b["x"], b["y"])])
        if ls.length < 1e-6: continue
        d = ls.distance(Point(v))
        if best is None or d < best[0]: best = (d, j, ls)
    if not best: return False
    d, j, ls = best; c = ls.interpolate(ls.project(Point(v)))
    nx, ny = c.x - v[0], c.y - v[1]; nl = math.hypot(nx, ny)
    if nl < 1e-6: return False
    for q in (r[j], r[j + 1]):
        q["x"] = round(q["x"] + nx / nl * shift, 5); q["y"] = round(q["y"] + ny / nl * shift, 5)
    return True
def detour(t, i, v, shift, half=0.15):
    """45-degree trapezoid on segment i stepping away from v by shift"""
    r = t["route"]; a, b = r[i], r[i + 1]
    ls = LineString([(a["x"], a["y"]), (b["x"], b["y"])]); L = ls.length
    s = ls.project(Point(v)); c = ls.interpolate(s)
    ux, uy = (b["x"] - a["x"]) / L, (b["y"] - a["y"]) / L
    nx, ny = c.x - v[0], c.y - v[1]; nl = math.hypot(nx, ny)
    if nl < 1e-6: nx, ny = -uy, ux
    else: nx, ny = nx / nl, ny / nl
    # step perpendicular to the segment, on the side away from the via
    px, py = -uy, ux
    if px * nx + py * ny < 0: px, py = -px, -py
    q0, q1, q2, q3 = s - half - shift, s - half, s + half, s + half + shift
    if q0 < 0.02 or q3 > L - 0.02: return False
    P_ = lambda q, o: dict(a, x=round(a["x"] + ux * q + px * o, 5), y=round(a["y"] + uy * q + py * o, 5))
    t["route"] = r[:i + 1] + [P_(q0, 0), P_(q1, shift), P_(q2, shift), P_(q3, 0)] + r[i + 1:]
    return True

def cost(ps):
    return sum(p[2] for p in ps if p[0] == "hole") + 10 * sum(1 for p in ps if p[0] == "gap")
def nearest_seg(t, l, v):
    r = t["route"]; best = None
    for j, (p0, p1) in enumerate(zip(r, r[1:])):
        if p0["route_type"] == p1["route_type"] == "wire" and p0["layer"] == p1["layer"] == l and (p0["x"], p0["y"]) != (p1["x"], p1["y"]):
            d = LineString([(p0["x"], p0["y"]), (p1["x"], p1["y"])]).distance(Point(v))
            if best is None or d < best[0]: best = (d, j)
    return best[1] if best else None
def variants(t, l, v, need, w):
    out = []
    for nk in (True, False):
        for op in ("none", "shift", "corner", "detour", "detour_s", "detour_l"):
            for extra in (0.006, 0.015, 0.03):
                if op == "none" and (not nk or extra > 0.006): continue
                out.append((nk, op, max(0, need - ((w - WMIN) / 2 if nk else 0)) + extra))
    return out
HALF = 0.15
def apply(t, l, v, nk, op, rem):
    global HALF
    HALF = {"detour_s": 0.06, "detour_l": 0.3}.get(op, 0.15)
    if op.startswith("detour"): op = "detour"
    if nk: neck_all(t, l, v)
    if op == "none" or rem <= 0: return True
    if op == "shift": return shift_seg(t, l, v, rem)
    if op == "corner": return corner(t, l, v, rem)
    j = nearest_seg(t, l, v)
    return j is not None and detour(t, j, v, rem, half=HALF)
fixed_n = 0
for pas in range(int(os.environ.get("PASSES", 3))):
    for k, t in enumerate(traces):
        others = geoms_except(k); skip = set()
        for attempt in range(60):
            ps = problems(k, others); c0 = cost(ps); g0 = sum(1 for p in ps if p[0] == "gap")
            hs = [p for p in ps if p[0] == "hole" and p[3] not in skip]
            if not hs: break
            kind, l, need, v, i = max(hs, key=lambda p: p[2])
            w = t["route"][i]["width"]; before = json.dumps(t["route"]); best = None
            for nk, op, rem in variants(t, l, v, need, w):
                t["route"] = json.loads(before)
                if not apply(t, l, v, nk, op, rem): continue
                a = problems(k, others)
                if sum(1 for p in a if p[0] == "gap") > g0: continue
                ca = cost(a)
                if ca < c0 - 1e-4 and (best is None or ca < best[0]): best = (ca, json.dumps(t["route"]))
            if best: t["route"] = json.loads(best[1]); fixed_n += 1
            else: t["route"] = json.loads(before); skip.add(v)
        if ddr_geoms(k) != ddr_cu[k]: ddr_cu[k] = ddr_geoms(k); rebuild()
    left = [(net_of(t), p) for k, t in enumerate(traces) for p in problems(k) if p[0] == "hole"]
    print(f"pass {pas}: {fixed_n} changes, {len({(n, p[3]) for n, p in left})} trace/via spots left", flush=True)
    if not left: break
# ---- last resort: move an offending DDR via (with the wire ends on it) by up to 0.05 mm ----
via_owner = {}
for m, t in enumerate(traces):
    for idx, p in enumerate(t["route"]):
        if p["route_type"] == "via":
            for j, vv in enumerate(vias):
                if abs(vv[0] - p["x"]) < 1e-6 and abs(vv[1] - p["y"]) < 1e-6 and vv[4] == net_of(t): via_owner.setdefault(j, []).append((m, idx))
def via_ok(j):
    """the via's hole keeps 0.2 mm from all other-net copper on every layer, 0.2 mm hole to hole"""
    x, y, d, h, vn = vias[j]; hg = Point(x, y).buffer(h / 2, 12)
    for l in LAY:
        tree, items = TREES[l]
        for q in tree.query(hg.buffer(HOLE)):
            if items[q][1] != vn and hg.distance(items[q][0]) < HOLE - EPS: return False
    for q in HOLE_TREE.query(hg.buffer(HOLE + 0.13)):
        if q != j and vias[q][4] != vn:
            ox, oy, od, oh, on = vias[q]
            if Point(ox, oy).buffer(od / 2, 12).distance(hg) < HOLE - EPS: return False
    return True
def move_via(j, dx, dy):
    global HOLE_TREE
    x, y, d, h, vn = vias[j]
    for m, idx in via_owner[j]:
        r = traces[m]["route"]
        for q in (idx - 1, idx, idx + 1):
            if 0 <= q < len(r) and abs(r[q]["x"] - x) < 1e-6 and abs(r[q]["y"] - y) < 1e-6:
                r[q]["x"] = round(r[q]["x"] + dx, 5); r[q]["y"] = round(r[q]["y"] + dy, 5)
    vias[j] = (x + dx, y + dy, d, h, vn); HOLES_G[j] = Point(x + dx, y + dy).buffer(h / 2, 12); HOLE_TREE = STRtree(HOLES_G)
    for m, idx in via_owner[j]: ddr_cu[m] = ddr_geoms(m)
    rebuild()
def near_traces(x, y):
    out = set()
    for l in LAY:
        tree, items = TREES[l]
        for q in tree.query(Point(x, y).buffer(0.6)):
            if items[q][2] is not None: out.add(items[q][2])
    return out
moved_v = 0
for rnd in range(3):
    spots = {(k, p[3]) for k in range(len(traces)) for p in problems(k) if p[0] == "hole"}
    for k, v in sorted(spots):
        js = [j for j in via_owner if abs(vias[j][0] - v[0]) < 1e-6 and abs(vias[j][1] - v[1]) < 1e-6]
        if not js: continue
        j = js[0]; x0, y0 = vias[j][0], vias[j][1]
        aff = near_traces(x0, y0) | {m for m, _ in via_owner[j]} | {k}
        c0 = sum(cost(problems(m)) for m in aff); g0 = sum(1 for m in aff for p in problems(m) if p[0] == "gap")
        snap = {m: json.dumps(traces[m]["route"]) for m in aff}; best = None
        for mag in (0.01, 0.02, 0.03, 0.04, 0.05, 0.065, 0.08, 0.1):
            for a in range(8):
                dx, dy = mag * math.cos(a * math.pi / 4), mag * math.sin(a * math.pi / 4)
                move_via(j, dx, dy)
                aff2 = aff | near_traces(x0 + dx, y0 + dy)
                ps = [p for m in aff2 for p in problems(m)]
                c1 = sum(p[2] for p in ps if p[0] == "hole") + 10 * sum(1 for p in ps if p[0] == "gap")
                g1 = sum(1 for p in ps if p[0] == "gap")
                if via_ok(j) and g1 <= g0 and c1 < c0 - 1e-4 and (best is None or c1 < best[0]): best = (c1, dx, dy)
                move_via(j, -dx, -dy)
                for m in aff: traces[m]["route"] = json.loads(snap[m])
                for m in aff: ddr_cu[m] = ddr_geoms(m)
                rebuild()
        if best: move_via(j, best[1], best[2]); moved_v += 1
left = [(net_of(t), p) for k, t in enumerate(traces) for p in problems(k) if p[0] == "hole"]
print(f"via moves: {moved_v}; {len({(n, p[3]) for n, p in left})} trace/via spots left")
json.dump(R, open(SRC, "w"))
for n, p in sorted({(n, (p[1], round(p[2], 3), (round(p[3][0] + RK[0], 2), round(p[3][1] + RK[1], 2)))) for n, p in left})[:30]: print("  left", n, p)
