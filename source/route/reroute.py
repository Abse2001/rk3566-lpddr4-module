# Strict single-net reroute on a finished board: the named nets are ripped up and routed again, one at a time, by A*
# on a 0.05 mm grid against the exact copper of every other net (no conflicts are ever accepted). A cell is free on a
# layer when its centre keeps GAP + w/2 from other copper there (pads, traces, vias), EDGE from the board edge and
# holes, and, for a fast net on top/bottom, the reference-plane distance from slow traces on the ground layer below.
# A via (through, 0.25/0.15 mm) needs that clearance on all six layers. A differential pair member is drawn to its
# partner: a step costs more when it is not running alongside the partner's trace (same layer, pair pitch).
# Usage: ROUTES=.. COPPER=.. NETS=a,b [LAYERS=top,inner3,bottom] [VIA_COST=1.0] [MARGIN_BOX=4] python3 reroute.py
import json, os, math, re, heapq
import numpy as np
import shapely
from shapely.geometry import Point, LineString, box
from shapely.ops import unary_union
D = os.path.dirname(os.path.abspath(__file__))
RP, CP = os.environ["ROUTES"], os.environ["COPPER"]
rt, cu = json.load(open(RP)), json.load(open(CP))
PD = json.load(open(D + "/../design/pads.json"))
pads, fvias = PD["pads"], [dict(v, net="GND") for v in PD["footprintVias"]]
GAP, EDGE, VD, H = 0.1, 0.25, 0.25, 0.0764
W = float(os.environ.get("W", 0.1))  # trace width (DDR: 0.11)
# inside BGA ball fields a trace may neck down to NECK_W (JLCPCB allows 0.09 mm, 3 mil in BGA fan-outs)
NECK_W = float(os.environ.get("NECK_W", W)); NECK_M = float(os.environ.get("NECK_M", 0.3)); NECK_REFS = os.environ.get("NECK_REFS", "U1,U2,U6").split(",")
G = 0.05; M = float(os.environ.get("M", 0.012))  # grid step, safety margin for grid moves
ALL = ["top", "inner1", "inner2", "inner3", "inner4", "bottom"]
LAY = os.environ.get("LAYERS", "top,inner3,bottom").split(",")
VIA_COST = float(os.environ.get("VIA_COST", 1.0)); BOXM = float(os.environ.get("MARGIN_BOX", 4))
FAST = re.compile(r"^(HDMI_TX_[CD]|MIPI_|PCIE20_|USB_OTG0_D|EMMC_|CM4_SD_|DDR_)")
BOARD = box(-3.5, -51.5, 36.5, 3.5); HOLES = [(0, 0), (33, 0), (0, -48), (33, -48)]

def partner(n):
    for a, b in (("P", "N"), ("N", "P"), ("DP", "DM"), ("DM", "DP")):
        m = re.match(rf"(.*){a}(_C)?$", n)
        if m:
            q = m.group(1) + b + (m.group(2) or "")
            if q in rt["nets"]: return q
    return None

def geoms(layer, skip):
    out = []
    for p in pads:
        if p["layer"] == layer and p["net"] != skip:
            out.append(Point(p["x"], p["y"]).buffer(p["w"] / 2, 16) if p["shape"] == "circle" and not os.environ.get("SQUARE_PADS") else box(p["x"] - p["w"] / 2, p["y"] - p["h"] / 2, p["x"] + p["w"] / 2, p["y"] + p["h"] / 2))
    for t in cu["traces"]:
        if t["layer"] == layer and t["net"] != skip and len(t["pts"]) > 1:
            out.append(LineString([(q["x"], q["y"]) for q in t["pts"]]).buffer(t["w"] / 2, 8))
    for v in cu["vias"] + fvias:
        if v["net"] != skip: out.append(Point(v["x"], v["y"]).buffer(v["d"] / 2 + (max(0, 0.2 - (v["d"] - v["hole"]) / 2 - GAP) if os.environ.get("HOLE_RULE") else 0), 12))  # hole rule
    return out

def route(net):
    tp = [p for p in pads if p["net"] == net]
    assert len(tp) == 2, (net, len(tp))
    # rip up
    cu["traces"] = [t for t in cu["traces"] if t["net"] != net]; cu["vias"] = [v for v in cu["vias"] if v["net"] != net]
    fast = bool(FAST.match(net))
    x0 = min(p["x"] for p in tp) - BOXM; x1 = max(p["x"] for p in tp) + BOXM
    y0 = min(p["y"] for p in tp) - BOXM; y1 = max(p["y"] for p in tp) + BOXM
    xs = np.arange(x0, x1, G); ys = np.arange(y0, y1, G); NX, NY = len(xs), len(ys)
    X, Y = np.meshgrid(xs, ys)
    win = box(x0 - 1, y0 - 1, x1 + 1, y1 + 1)
    edge = BOARD.exterior.buffer(EDGE + W / 2 + M).union(unary_union([Point(h).buffer(1.35 + EDGE + W / 2 + M) for h in HOLES]))
    outside = ~shapely.contains_xy(BOARD, X, Y) | shapely.contains_xy(edge, X, Y)
    free, viaok = {}, ~outside.copy()
    nb = []
    for ref in NECK_REFS:
        ps_ = [p for p in pads if p["ref"] == ref]
        if ps_: nb.append(box(min(p["x"] for p in ps_) - NECK_M, min(p["y"] for p in ps_) - NECK_M, max(p["x"] for p in ps_) + NECK_M, max(p["y"] for p in ps_) + NECK_M))
    inneck = shapely.contains_xy(unary_union(nb), X, Y) if nb else np.zeros_like(outside)
    eviaedge = BOARD.exterior.buffer(EDGE + VD / 2 + M).union(unary_union([Point(h).buffer(1.35 + EDGE + VD / 2 + M) for h in HOLES]))
    viaok &= ~shapely.contains_xy(eviaedge, X, Y)
    for l in ALL:
        obs = [g for g in geoms(l, net) if g.intersects(win)]
        u = unary_union(obs) if obs else None
        if l in LAY:
            blk = u.buffer(GAP + W / 2 + M, 8) if u is not None else None
            f = ~outside & (~shapely.contains_xy(blk, X, Y) if blk is not None else True)
            if NECK_W < W and u is not None:
                fn = ~outside & ~shapely.contains_xy(u.buffer(GAP + NECK_W / 2 + M, 8), X, Y)
                f = np.where(inneck, fn, f)
            if fast and l in ("top", "bottom"):
                gl = "inner1" if l == "top" else "inner4"
                slow = [LineString([(q["x"], q["y"]) for q in t["pts"]]).buffer(t["w"] / 2) for t in cu["traces"] if t["layer"] == gl and t["net"] != "GND" and len(t["pts"]) > 1]
                slow = [g for g in slow if g.intersects(win)]
                if slow: f &= ~shapely.contains_xy(unary_union(slow).buffer(W / 2 + 3 * H + M), X, Y)
            free[l] = f
        if u is not None: viaok &= ~shapely.contains_xy(u.buffer((max(GAP + VD / 2, 0.2 + 0.15 / 2) if os.environ.get("HOLE_RULE") else GAP + VD / 2) + M, 8), X, Y)  # hole 0.2 mm from copper
    # via holes keep 0.2 mm from other holes (edge to edge)
    hs = [Point(v["x"], v["y"]) for v in cu["vias"] + fvias if v["net"] != net]
    if hs: viaok &= ~shapely.contains_xy(unary_union(hs).buffer(0.2 + 0.15 + M), X, Y)
    for l in LAY: viaok &= free[l] | ~free[l]  # (shape only)
    # partner attraction: cells at pair pitch from the partner's trace on the same layer
    pn = partner(net); near = {}
    for l in LAY:
        segs = [t for t in cu["traces"] if pn and t["net"] == pn and t["layer"] == l and len(t["pts"]) > 1]
        if segs:
            pl = unary_union([LineString([(q["x"], q["y"]) for q in t["pts"]]) for t in segs])
            near[l] = shapely.contains_xy(pl.buffer(0.26), X, Y)
        else: near[l] = np.zeros_like(outside)
    gi = lambda x: int(round((x - x0) / G)); gj = lambda y: int(round((y - y0) / G))
    L = {l: k for k, l in enumerate(LAY)}
    def term(p):
        ls = [p["layer"]] if p["layer"] in L else []
        return [(L[l], gj(p["y"]), gi(p["x"])) for l in ls]
    S, T = term(tp[0]), term(tp[1])
    assert S and T, (net, tp)
    for (l, j, i) in S + T: free[LAY[l]][j, i] = True  # the pad centre itself
    tj, ti = T[0][1], T[0][2]
    h = lambda j, i: G * math.hypot(j - tj, i - ti)
    dist = {}; prev = {}; pq = []
    for s in S: dist[s] = 0.0; heapq.heappush(pq, (h(s[1], s[2]), 0.0, s))
    goal = set(T); D8 = [(0, 1), (1, 0), (0, -1), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)]
    found = None
    while pq:
        f_, g_, s = heapq.heappop(pq)
        if g_ > dist.get(s, 1e9): continue
        if s in goal: found = s; break
        l, j, i = s
        fl = free[LAY[l]]
        for dj, di in D8:
            jj, ii = j + dj, i + di
            if not (0 <= jj < NY and 0 <= ii < NX) or not fl[jj, ii]: continue
            if dj and di and not (fl[j, ii] or fl[jj, i]): continue
            c = G * (1.414 if dj and di else 1.0) * (1.0 if near[LAY[l]][jj, ii] or not pn else 1.6)
            ns = (l, jj, ii); nd = g_ + c
            if nd < dist.get(ns, 1e9): dist[ns] = nd; prev[ns] = s; heapq.heappush(pq, (nd + h(jj, ii), nd, ns))
        if viaok[j, i]:
            for l2 in range(len(LAY)):
                if l2 != l and free[LAY[l2]][j, i]:
                    ns = (l2, j, i); nd = g_ + VIA_COST
                    if nd < dist.get(ns, 1e9): dist[ns] = nd; prev[ns] = s; heapq.heappush(pq, (nd + h(j, i), nd, ns))
    if not found:
        reach = {}
        for (l_, j_, i_) in dist: reach[LAY[l_]] = reach.get(LAY[l_], 0) + 1
        print("FAILED", net, "reached cells per layer:", reach, "start free:", [bool(free[LAY[s_[0]]][s_[1], s_[2]]) for s_ in S], "goal via ok:", [bool(viaok[t_[1], t_[2]]) for t_ in T]); return False
    path = [found]
    while path[-1] in prev: path.append(prev[path[-1]])
    path.reverse()
    segs, vias, cur = [], [], [path[0]]
    nk = lambda q: bool(inneck[q[1], q[2]]) and NECK_W < W
    zone = [nk(path[0])]; z = zone[0]
    for a, b in zip(path, path[1:]):
        if a[0] != b[0]:
            segs.append((a[0], cur)); vias.append(a); cur = [b]; z = nk(b); zone.append(z)
        elif nk(b) != z and len(cur) > 1:
            segs.append((a[0], cur)); cur = [a, b]; z = nk(b); zone.append(z)  # width change at the ball-field edge
        else: cur.append(b)
    segs.append((cur[0][0], cur))
    def simp(c):
        pts = [(x0 + q[2] * G, y0 + q[1] * G) for q in c]
        out = [pts[0]]
        for k in range(1, len(pts) - 1):
            a, b, d = out[-1], pts[k], pts[k + 1]
            if abs((b[0] - a[0]) * (d[1] - b[1]) - (b[1] - a[1]) * (d[0] - b[0])) > 1e-9: out.append(b)
        if len(pts) > 1: out.append(pts[-1])
        return [{"x": round(x, 4), "y": round(y, 4)} for x, y in out]
    # snap the ends to the exact pad centres
    rsegs = []
    for (l, c), zn in zip(segs, zone):
        pts = simp(c)
        if len(pts) < 2: continue
        rsegs.append({"layer": LAY[l], "w": NECK_W if zn else W, "pts": pts})
    for p in tp:
        for s in rsegs:
            for e in (0, -1):
                q = s["pts"][e]
                if s["layer"] == p["layer"] and abs(q["x"] - p["x"]) < G and abs(q["y"] - p["y"]) < G: s["pts"][e] = {"x": p["x"], "y": p["y"]}
    rv = [{"x": round(x0 + v[2] * G, 4), "y": round(y0 + v[1] * G, 4), "d": VD, "hole": 0.15, "net": net} for v in vias]
    rt["nets"][net] = {"segs": rsegs, "vias": rv}
    cu["traces"] += [dict(s, net=net) for s in rsegs]; cu["vias"] += rv
    Lm = sum(math.hypot(b["x"] - a["x"], b["y"] - a["y"]) for s in rsegs for a, b in zip(s["pts"], s["pts"][1:])) + 0.6 * len(rv)
    print(f"routed {net}: {Lm:.2f} mm, {len(rv)} vias, layers {[s['layer'] for s in rsegs]}")
    return True

# rip every listed net first, so the first one routed does not detour around the old copper of the others
NL_ = os.environ["NETS"].split(",")
cu["traces"] = [t for t in cu["traces"] if t["net"] not in NL_]; cu["vias"] = [v for v in cu["vias"] if v["net"] not in NL_]
ok_all = all([route(n) for n in NL_])
if not ok_all: print("FAILED: not all nets routed")
json.dump(rt, open(RP, "w")); json.dump(cu, open(CP, "w"))
