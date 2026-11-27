# From a rail via that its island cannot reach, find on LAYER (default bottom) every spot a W trace can reach with
# GAP clearance, keep those where a new via clears all other-net copper on every layer by C (hole rule: 0.275),
# take the one nearest the rail's main inner2 island, add the via and the (straightened) trace to COPPER.
# planes.py then claims an inner2 corridor from the island to the new via.
import json, os, sys, math, numpy as np, shapely
from collections import deque
from shapely.geometry import Point, LineString, box, Polygon
from shapely.ops import unary_union
S = os.path.dirname(os.path.abspath(__file__)) + "/.."
F, NET = sys.argv[1], sys.argv[2]; sx, sy = float(sys.argv[3]), float(sys.argv[4])
LAY = os.environ.get("LAYER", "bottom"); W, GAP, G, M = float(os.environ.get("W", 0.1)), 0.1, 0.025, 0.002; C = float(os.environ.get("C", 0.235)); R = float(os.environ.get("R", 6))
cu = json.load(open(F + "/copper.json")); pl = json.load(open(F + "/planes.json")); P = json.load(open(S + "/design/pads.json"))
isl = unary_union([Polygon([(a["x"], a["y"]) for a in q["outer"]], [[(a["x"], a["y"]) for a in h] for h in q["holes"]]).buffer(0) for q in pl if q["layer"] == "inner2" and q["net"] == NET])
main = max(getattr(isl, "geoms", [isl]), key=lambda g: g.area)
x0, x1, y0, y1 = sx - R, sx + R, sy - R, sy + R; win = box(x0 - 1, y0 - 1, x1 + 1, y1 + 1)
xs = np.arange(x0, x1, G); ys = np.arange(y0, y1, G); X, Y = np.meshgrid(xs, ys)
def obst(lay):
    o = [Point(p["x"], p["y"]).buffer(p["w"] / 2) if p["shape"] == "circle" else box(p["x"] - p["w"] / 2, p["y"] - p["h"] / 2, p["x"] + p["w"] / 2, p["y"] + p["h"] / 2) for p in P["pads"] if p["net"] != NET and (lay is None or p["layer"] == lay)]
    o += [LineString([(a["x"], a["y"]) for a in t["pts"]]).buffer(t["w"] / 2) for t in cu["traces"] if t["net"] != NET and len(t["pts"]) > 1 and (lay is None or t["layer"] == lay)]
    o += [Point(v["x"], v["y"]).buffer(v["d"] / 2) for v in cu["vias"] + P["footprintVias"] if v.get("net", "GND") != NET]
    return unary_union([g for g in o if g.intersects(win)])
u = obst(LAY); clr = u.buffer(GAP + W / 2 + M); free = ~shapely.contains_xy(clr, X, Y)
ua = obst(None); viaok = ~shapely.contains_xy(ua.buffer(C), X, Y)
# inner2: the via must not sit in another rail's island interior (its corridor would cut it); GND layers are cleared by planes.py
oth = unary_union([Polygon([(a["x"], a["y"]) for a in q["outer"]]).buffer(0) for q in pl if q["layer"] == "inner2" and q["net"] != NET])
si, sj = int(round((sy - y0) / G)), int(round((sx - x0) / G)); prev = {(si, sj): None}; q = deque([(si, sj)])
while q:
    i, j = q.popleft()
    for di, dj in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
        a, b = i + di, j + dj
        if 0 <= a < free.shape[0] and 0 <= b < free.shape[1] and free[a, b] and (a, b) not in prev: prev[(a, b)] = (i, j); q.append((a, b))
own = [v for v in cu['vias'] if v['net'] == NET and abs(v['x'] - sx) < R + 1 and abs(v['y'] - sy) < R + 1]
best = None
for (i, j) in prev:
    if not viaok[i, j] or Y[i, j] < float(os.environ.get("YMIN", -99)) or any(math.hypot(X[i, j] - v["x"], Y[i, j] - v["y"]) < 0.45 for v in own): continue
    pt = Point(X[i, j], Y[i, j]); d = main.distance(pt) + (0.5 if oth.contains(pt) else 0)
    if best is None or d < best[0]: best = (d, (i, j))
if not best: sys.exit("no reachable via spot")
path = []; c = best[1]
while c: path.append((float(X[c]), float(Y[c]))); c = prev[c]
path = path[::-1]; path[0] = (sx, sy)
out = [path[0]]; k = 0
while k < len(path) - 1:
    m = len(path) - 1
    while m > k + 1 and LineString([path[k], path[m]]).buffer(W / 2).intersects(u.buffer(GAP)): m -= 1
    out.append(path[m]); k = m
assert not LineString(out).buffer(W / 2).intersects(u.buffer(GAP - 1e-4)), "path not clear"
vx, vy = round(out[-1][0], 4), round(out[-1][1], 4); out[-1] = (vx, vy)
cu["traces"].append({"pts": [{"x": round(x, 4), "y": round(y, 4)} for x, y in out], "layer": LAY, "w": W, "net": NET})
cu["vias"].append({"x": vx, "y": vy, "d": 0.25, "hole": 0.15, "net": NET})
json.dump(cu, open(F + "/copper.json", "w"))
print(f"{NET}: ({sx},{sy}) -> via ({vx},{vy}) on {LAY}, {LineString(out).length:.2f} mm, {best[0]:.2f} mm from the island")
