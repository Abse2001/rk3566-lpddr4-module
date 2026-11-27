# Removes "via hops" from differential pairs whose P and N have different via counts: a hop is two vias of one
# member joined by a short trace on another layer, with the member on the same layer before and after (it dropped
# down to dodge something and came back up). The hop is replaced by a trace on that layer between the two via
# spots, found by a BFS in a small box (W wide, >= GAP from all other-net copper on that layer and from every
# other-net via). Only the hop changes; the rest of the pair is untouched. Each removed hop saves two vias.
# Usage: COPPER=final/copper.json ROUTES=final/routes.json [PAIRS=P1,P2] python3 hop_fix.py   (rewrites both)
import json, os, re, math, collections
import numpy as np, shapely
from collections import deque
from shapely.geometry import Point, LineString, box
from shapely.ops import unary_union
D = os.path.dirname(os.path.abspath(__file__))
CP, RP = os.environ["COPPER"], os.environ["ROUTES"]
cu, rt = json.load(open(CP)), json.load(open(RP))
P = json.load(open(D + "/../design/pads.json")); pads, fvias = P["pads"], P["footprintVias"]
GAP, G, M = 0.1, 0.025, 0.002
key = lambda x, y: (round(x, 3), round(y, 3))
def pairs():
    names = {t["net"] for t in cu["traces"]}; out = []
    for n in sorted(names):
        m = re.match(r"(.*?)(P|_P|DP)(_C)?$", n)
        if m and not n.startswith("DDR_"):
            q = m.group(1) + {"P": "N", "_P": "_N", "DP": "DM"}[m.group(2)] + (m.group(3) or "")
            vc = lambda k: len({key(v["x"], v["y"]) for v in cu["vias"] if v["net"] == k})
            if q in names and vc(n) != vc(q): out.append((n, q))
    return out
def hops(net):
    """(via1, via2, inner trace) for each hop of the net"""
    vs = {key(v["x"], v["y"]): v for v in cu["vias"] if v["net"] == net}
    at = collections.defaultdict(list)  # via key -> traces ending on it
    for t in cu["traces"]:
        if t["net"] != net: continue
        for q in (t["pts"][0], t["pts"][-1]):
            k = key(q["x"], q["y"])
            if k in vs: at[k].append(t)
    out = []
    for t in cu["traces"]:
        if t["net"] != net: continue
        a, b = key(t["pts"][0]["x"], t["pts"][0]["y"]), key(t["pts"][-1]["x"], t["pts"][-1]["y"])
        if a in vs and b in vs and a != b:
            la = {u["layer"] for u in at[a] if u is not t}; lb = {u["layer"] for u in at[b] if u is not t}
            for L in la & lb:
                if L != t["layer"]: out.append((vs[a], vs[b], t, L))
    return out
def route_on(layer, net, w, a, b, extra=0.8):
    x0, x1 = min(a[0], b[0]) - extra, max(a[0], b[0]) + extra; y0, y1 = min(a[1], b[1]) - extra, max(a[1], b[1]) + extra
    win = box(x0 - 0.5, y0 - 0.5, x1 + 0.5, y1 + 0.5)
    obs = [Point(p["x"], p["y"]).buffer(p["w"] / 2) if p["shape"] == "circle" else box(p["x"] - p["w"] / 2, p["y"] - p["h"] / 2, p["x"] + p["w"] / 2, p["y"] + p["h"] / 2) for p in pads if p["net"] != net and p["layer"] == layer]
    obs += [LineString([(q["x"], q["y"]) for q in t["pts"]]).buffer(t["w"] / 2) for t in cu["traces"] if t["net"] != net and t["layer"] == layer and len(t["pts"]) > 1]
    obs += [Point(v["x"], v["y"]).buffer(v["d"] / 2) for v in cu["vias"] + [dict(v, net="GND") for v in fvias] if v["net"] != net]
    u = unary_union([g for g in obs if g.intersects(win)])
    clr = u.buffer(GAP + w / 2 + M)
    xs = np.arange(x0, x1, G); ys = np.arange(y0, y1, G); X, Y = np.meshgrid(xs, ys)
    free = ~shapely.contains_xy(clr, X, Y)
    si, sj = int(round((a[1] - y0) / G)), int(round((a[0] - x0) / G))
    prev = {(si, sj): None}; q = deque([(si, sj)]); end = None
    while q:
        i, j = q.popleft()
        if math.hypot(X[i, j] - b[0], Y[i, j] - b[1]) < 0.06: end = (i, j); break
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            ii, jj = i + di, j + dj
            if 0 <= ii < free.shape[0] and 0 <= jj < free.shape[1] and free[ii, jj] and (ii, jj) not in prev: prev[(ii, jj)] = (i, j); q.append((ii, jj))
    if end is None: return None
    path = []; c = end
    while c: path.append((float(X[c]), float(Y[c]))); c = prev[c]
    path = path[::-1]; path[0] = a; path[-1] = b
    pts = [path[0]]; k = 0  # straighten
    while k < len(path) - 1:
        m = len(path) - 1
        while m > k + 1 and LineString([path[k], path[m]]).buffer(w / 2).intersects(u.buffer(GAP)): m -= 1
        pts.append(path[m]); k = m
    if LineString(pts).buffer(w / 2).intersects(u.buffer(GAP - 1e-4)): return None
    return pts
todo = pairs()
if os.environ.get("PAIRS"): todo = [pq for pq in todo if pq[0] in os.environ["PAIRS"].split(",")]
for P_, N_ in todo:
    for net in (P_, N_):
        for v1, v2, t, L in hops(net):
            w = max(t["w"], 0.1)
            for extra in (0.8, 1.5):
                pts = route_on(L, net, w, (v1["x"], v1["y"]), (v2["x"], v2["y"]), extra)
                if pts: break
            if not pts: print(f"{net}: hop {key(v1['x'], v1['y'])} -> {key(v2['x'], v2['y'])} on {t['layer']} kept (no room on {L})"); continue
            cu["traces"].remove(t)
            cu["vias"] = [v for v in cu["vias"] if not (v["net"] == net and key(v["x"], v["y"]) in (key(v1["x"], v1["y"]), key(v2["x"], v2["y"])))]
            cu["traces"].append({"pts": [{"x": round(x, 4), "y": round(y, 4)} for x, y in pts], "layer": L, "w": w, "net": net})
            print(f"{net}: hop {key(v1['x'], v1['y'])} -> {key(v2['x'], v2['y'])} via {t['layer']} replaced by a {LineString(pts).length:.2f} mm trace on {L}")
# routes.json follows the copper
for n in rt["nets"]:
    rt["nets"][n] = {"segs": [dict(t) for t in cu["traces"] if t["net"] == n], "vias": [dict(v) for v in cu["vias"] if v["net"] == n]}
json.dump(cu, open(CP, "w")); json.dump(rt, open(RP, "w"))
vc = lambda k: len({key(v["x"], v["y"]) for v in cu["vias"] if v["net"] == k})
for P_, N_ in todo: print(f"{P_}: vias {vc(P_)}/{vc(N_)}")
