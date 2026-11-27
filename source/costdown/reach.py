# BFS reachability for a W-wide trace (GAP to other-net copper) on one layer from a start point; prints how far
# it gets toward a target and the cells reachable, to see what blocks a join.
import json, os, sys, math, numpy as np, shapely
from collections import deque
from shapely.geometry import Point, LineString, box
from shapely.ops import unary_union
S = os.path.dirname(os.path.abspath(__file__)) + "/.."
F, NET = sys.argv[1], sys.argv[2]; sx, sy, tx, ty = map(float, sys.argv[3:7]); W, GAP, G = 0.1, 0.1, 0.025
cu = json.load(open(F + "/copper.json")); P = json.load(open(S + "/design/pads.json"))
x0, x1, y0, y1 = min(sx, tx) - 2, max(sx, tx) + 2, min(sy, ty) - 2, max(sy, ty) + 2
xs = np.arange(x0, x1, G); ys = np.arange(y0, y1, G); X, Y = np.meshgrid(xs, ys)
for lay in ["top", "inner3", "bottom", "inner1", "inner4"]:
    obs = [Point(p["x"], p["y"]).buffer(p["w"] / 2) if p["shape"] == "circle" else box(p["x"] - p["w"] / 2, p["y"] - p["h"] / 2, p["x"] + p["w"] / 2, p["y"] + p["h"] / 2) for p in P["pads"] if p["net"] != NET and p["layer"] == lay]
    obs += [LineString([(a["x"], a["y"]) for a in t["pts"]]).buffer(t["w"] / 2) for t in cu["traces"] if t["net"] != NET and len(t["pts"]) > 1 and t["layer"] == lay]
    obs += [Point(v["x"], v["y"]).buffer(v["d"] / 2) for v in cu["vias"] + P["footprintVias"] if v.get("net", "GND") != NET]
    u = unary_union([g for g in obs if g.intersects(box(x0, y0, x1, y1))])
    free = ~shapely.contains_xy(u.buffer(GAP + W / 2), X, Y)
    si, sj = int(round((sy - y0) / G)), int(round((sx - x0) / G))
    seen = np.zeros_like(free); q = deque([(si, sj)]); seen[si, sj] = True
    while q:
        i, j = q.popleft()
        for di, dj in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
            a, b = i + di, j + dj
            if 0 <= a < free.shape[0] and 0 <= b < free.shape[1] and free[a, b] and not seen[a, b]: seen[a, b] = True; q.append((a, b))
    d = np.where(seen, np.hypot(X - tx, Y - ty), 99)
    k = np.unravel_index(np.argmin(d), d.shape)
    print(f"{lay}: reachable cells {int(seen.sum())}, closest to target {d[k]:.2f} mm at ({X[k]:.2f},{Y[k]:.2f})")
# JOIN=bottom: trace the BFS path on that layer (shortest in steps, then straightened) and add it to COPPER
if os.environ.get("JOIN"):
    lay = os.environ["JOIN"]
    obs = [Point(p["x"], p["y"]).buffer(p["w"] / 2) if p["shape"] == "circle" else box(p["x"] - p["w"] / 2, p["y"] - p["h"] / 2, p["x"] + p["w"] / 2, p["y"] + p["h"] / 2) for p in P["pads"] if p["net"] != NET and p["layer"] == lay]
    obs += [LineString([(a["x"], a["y"]) for a in t["pts"]]).buffer(t["w"] / 2) for t in cu["traces"] if t["net"] != NET and len(t["pts"]) > 1 and t["layer"] == lay]
    obs += [Point(v["x"], v["y"]).buffer(v["d"] / 2) for v in cu["vias"] + P["footprintVias"] if v.get("net", "GND") != NET]
    u = unary_union([g for g in obs if g.intersects(box(x0, y0, x1, y1))]); clr = u.buffer(GAP + W / 2 + float(os.environ.get("M", 0.001)))
    free = ~shapely.contains_xy(clr, X, Y)
    si, sj = int(round((sy - y0) / G)), int(round((sx - x0) / G)); ti, tj = int(round((ty - y0) / G)), int(round((tx - x0) / G))
    prev = {(si, sj): None}; q = deque([(si, sj)]); end = None
    while q and end is None:
        i, j = q.popleft()
        if math.hypot(X[i, j] - tx, Y[i, j] - ty) < 0.1: end = (i, j); break
        for di, dj in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
            a, b = i + di, j + dj
            if 0 <= a < free.shape[0] and 0 <= b < free.shape[1] and free[a, b] and (a, b) not in prev: prev[(a, b)] = (i, j); q.append((a, b))
    if end is None:
        sn = np.zeros(free.shape, bool)
        for (a, b) in prev: sn[a, b] = True
        dd = np.where(sn, np.hypot(X - tx, Y - ty), 99); kk = np.unravel_index(np.argmin(dd), dd.shape)
        sys.exit(f'JOIN blocked: closest {dd[kk]:.2f} at ({X[kk]:.2f},{Y[kk]:.2f}), {len(prev)} cells')
    path = []; c = end
    while c: path.append((float(X[c]), float(Y[c]))); c = prev[c]
    path = path[::-1]; path[0] = (sx, sy)
    # straighten: greedy longest clear segment
    out = [path[0]]; k = 0
    while k < len(path) - 1:
        m = len(path) - 1
        while m > k + 1 and LineString([path[k], path[m]]).intersects(clr): m -= 1
        out.append(path[m]); k = m
    seg = LineString(out); assert not seg.buffer(W / 2).buffer(GAP).intersects(u), "path not clear"
    cu["traces"].append({"pts": [{"x": round(x, 4), "y": round(y, 4)} for x, y in out], "layer": lay, "w": W, "net": NET})
    json.dump(cu, open(F + "/copper.json", "w")); print(f"joined on {lay}: {len(out)} points, {seg.length:.2f} mm")
