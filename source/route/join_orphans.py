# Supply-rail vias their plane island does not reach. Under the SoC the rails' balls interleave, and a lone ball of
# one rail can end up enclosed by another rail's island; planes.py then cannot reach its via, and the router assumed
# every rail via is joined by its plane. Each such via is joined here to its own rail's copper that the island does
# reach: a strict A* on a 0.05 mm grid over top / inner3 / bottom (exact clearance from every other net's pads,
# traces and vias, board edge), ending on any same-net pad, via or trace connected to the island. The trace is
# 0.1 mm (signal width, as power traces are inside ball fields).
# Usage: COPPER=copper.json PLANES=planes.json python3 join_orphans.py   (adds the joins to COPPER; rerun planes.py
#        and check.py afterwards)
import json, os, heapq, math
import numpy as np
import shapely
from shapely.geometry import Point, LineString, box, Polygon
from shapely.ops import unary_union
D = os.path.dirname(os.path.abspath(__file__))
CP, PL = os.environ["COPPER"], os.environ["PLANES"]
cu, pl = json.load(open(CP)), json.load(open(PL))
P = json.load(open(D + "/../design/pads.json")); pads = P["pads"]; fvias = [dict(v, net="GND") for v in P["footprintVias"]]
GAP, W, M, G = 0.1, 0.1, 0.01, 0.05
LAY = ["top", "inner3", "bottom"]
padg = lambda p: Point(p["x"], p["y"]).buffer(p["w"] / 2, 16) if p["shape"] == "circle" else box(p["x"] - p["w"] / 2, p["y"] - p["h"] / 2, p["x"] + p["w"] / 2, p["y"] + p["h"] / 2)
islands = {}
for q in pl:
    if q["layer"] == "inner2":
        islands.setdefault(q["net"], []).append(Polygon([(a["x"], a["y"]) for a in q["outer"]], [[(a["x"], a["y"]) for a in h] for h in q["holes"]]).buffer(0))
added = 0
for net, polys in islands.items():
    isl = unary_union(polys)
    vs = [v for v in cu["vias"] if v["net"] == net]
    orphans = [v for v in vs if not isl.contains(Point(v["x"], v["y"]))]
    reached = [v for v in vs if isl.contains(Point(v["x"], v["y"]))]
    for v in orphans:
        # targets: same-net pads / vias the island reaches (their copper on the signal layers)
        tgt = {l: unary_union([Point(r["x"], r["y"]).buffer(r["d"] / 2) for r in reached] + [padg(p) for p in pads if p["net"] == net and p["layer"] == l and any(math.hypot(p["x"] - r["x"], p["y"] - r["y"]) < 0.15 for r in reached)]) for l in LAY}
        x0, x1, y0, y1 = v["x"] - 2, v["x"] + 2, v["y"] - 2, v["y"] + 2
        xs = np.arange(x0, x1, G); ys = np.arange(y0, y1, G); X, Y = np.meshgrid(xs, ys); NY, NX = X.shape
        win = box(x0 - 0.5, y0 - 0.5, x1 + 0.5, y1 + 0.5)
        free, goal = {}, {}
        for l in LAY:
            obs = [padg(p) for p in pads if p["layer"] == l and p["net"] != net]
            obs += [LineString([(a["x"], a["y"]) for a in t["pts"]]).buffer(t["w"] / 2) for t in cu["traces"] if t["layer"] == l and t["net"] != net and len(t["pts"]) > 1]
            obs += [Point(o["x"], o["y"]).buffer(o["d"] / 2) for o in cu["vias"] + fvias if o["net"] != net]
            u = unary_union([g for g in obs if g.intersects(win)])
            free[l] = ~shapely.contains_xy(u.buffer(GAP + W / 2 + M), X, Y)
            goal[l] = shapely.contains_xy(tgt[l], X, Y) & free[l]
        si, sj = int(round((v["x"] - x0) / G)), int(round((v["y"] - y0) / G))
        dist, prev, pq = {}, {}, []
        for k in range(len(LAY)):
            free[LAY[k]][sj, si] = True
            dist[(k, sj, si)] = 0; heapq.heappush(pq, (0, (k, sj, si)))
        found = None
        while pq:
            d, s = heapq.heappop(pq)
            if d > dist.get(s, 1e9): continue
            k, j, i = s
            if goal[LAY[k]][j, i] and d > 0: found = s; break
            for dj, di in ((0, 1), (1, 0), (0, -1), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                jj, ii = j + dj, i + di
                if not (0 <= jj < NY and 0 <= ii < NX) or not free[LAY[k]][jj, ii]: continue
                if dj and di and not (free[LAY[k]][j, ii] or free[LAY[k]][jj, i]): continue
                nd = d + G * (1.414 if dj and di else 1)
                if nd < dist.get((k, jj, ii), 1e9): dist[(k, jj, ii)] = nd; prev[(k, jj, ii)] = s; heapq.heappush(pq, (nd, (k, jj, ii)))
        if not found: print(f"{net}: via ({v['x']:.2f},{v['y']:.2f}) NOT joined"); continue
        path = [found]
        while path[-1] in prev: path.append(prev[path[-1]])
        pts = [{"x": round(x0 + q[2] * G, 4), "y": round(y0 + q[1] * G, 4)} for q in reversed(path)]
        pts[0] = {"x": v["x"], "y": v["y"]}
        cu["traces"].append({"net": net, "layer": LAY[found[0]], "w": W, "pts": pts})
        added += 1
        print(f"{net}: via ({v['x']:.2f},{v['y']:.2f}) joined on {LAY[found[0]]}, {dist[found]:.2f} mm")
json.dump(cu, open(CP, "w"))
print("joins:", added)
