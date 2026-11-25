# Inner-layer copper for the RK3566 module.
#   inner1, inner4: solid ground, cleared around every via that is not ground.
#   inner2: one island per supply rail. Each rail first claims a corridor joining all of its vias (so the island
#           is one piece), shortest corridors first; then every remaining free cell goes to the nearest island.
#           Islands keep >= 0.25 mm from each other, 0.2 mm from foreign vias and inner2 traces, 0.3 mm from the
#           board edge and the mounting holes.
# Input: copper.json (fixed + routed copper). Output: planes.json [{layer, net, outer, holes, area}]
import json, os, heapq, math
import numpy as np
from shapely.geometry import Point, LineString, box, Polygon, MultiPolygon
from shapely.ops import unary_union
D = os.path.dirname(os.path.abspath(__file__))
cu = json.load(open(D + "/copper.json"))
BOARD = box(-3.5, -51.5, 36.5, 3.5)
HOLES = [(0, 0), (33, 0), (0, -48), (33, -48)]
CLR, EDGE, SPLIT = 0.2, 0.3, 0.25
RAILS = ["VDD_CPU", "VDD_LOGIC", "VDD_GPU", "VDD_NPU", "VCC_DDR", "VCC3V3_SYS", "VCC5V0_SYS"]
outline = BOARD.buffer(-EDGE).difference(unary_union([Point(h).buffer(1.35 + EDGE) for h in HOLES]))

def via_disc(v, extra):
    return Point(v["x"], v["y"]).buffer(v["d"] / 2 + extra, 16)

out = []
def emit(layer, net, geom):
    geoms = geom.geoms if isinstance(geom, MultiPolygon) else [geom]
    for g in geoms:
        if g.is_empty or g.area < 0.05: continue
        out.append({"layer": layer, "net": net, "area": round(g.area, 3),
                    "outer": [{"x": round(x, 4), "y": round(y, 4)} for x, y in list(g.exterior.coords)[:-1]],
                    "holes": [[{"x": round(x, 4), "y": round(y, 4)} for x, y in list(r.coords)[:-1]] for r in g.interiors]})

# ---------------- ground planes ----------------
foreign = unary_union([via_disc(v, CLR) for v in cu["vias"] if v["net"] != "GND"])
gnd = outline.difference(foreign)
for layer in ("inner1", "inner4"):
    emit(layer, "GND", gnd)

# ---------------- inner2 islands ----------------
P = 0.05
X0, Y0, NX, NY = -3.5, -51.5, 801, 1101
xs = X0 + np.arange(NX) * P; ys = Y0 + np.arange(NY) * P
XX, YY = np.meshgrid(xs, ys)
# cells where no island copper may be: edge/holes, foreign vias (per rail), inner2 traces of other nets
free_all = np.ones((NY, NX), bool)
free_all &= (XX > -3.5 + EDGE) & (XX < 36.5 - EDGE) & (YY > -51.5 + EDGE) & (YY < 3.5 - EDGE)
for hx, hy in HOLES: free_all &= np.hypot(XX - hx, YY - hy) > 1.35 + EDGE
def stamp_disc(mask, x, y, r, val):
    i0, i1 = max(0, int((x - r - X0) / P) - 1), min(NX - 1, int((x + r - X0) / P) + 2)
    j0, j1 = max(0, int((y - r - Y0) / P) - 1), min(NY - 1, int((y + r - Y0) / P) + 2)
    sub = np.hypot(XX[j0:j1 + 1, i0:i1 + 1] - x, YY[j0:j1 + 1, i0:i1 + 1] - y) < r
    mask[j0:j1 + 1, i0:i1 + 1][sub] = val
def stamp_seg(mask, a, b, r, val):
    x0, x1 = sorted((a["x"], b["x"])); y0, y1 = sorted((a["y"], b["y"]))
    i0, i1 = max(0, int((x0 - r - X0) / P) - 1), min(NX - 1, int((x1 + r - X0) / P) + 2)
    j0, j1 = max(0, int((y0 - r - Y0) / P) - 1), min(NY - 1, int((y1 + r - Y0) / P) + 2)
    X, Y = XX[j0:j1 + 1, i0:i1 + 1], YY[j0:j1 + 1, i0:i1 + 1]
    vx, vy = b["x"] - a["x"], b["y"] - a["y"]; L = vx * vx + vy * vy
    k = np.clip(((X - a["x"]) * vx + (Y - a["y"]) * vy) / L, 0, 1) if L else 0
    d = np.hypot(X - a["x"] - k * vx, Y - a["y"] - k * vy)
    mask[j0:j1 + 1, i0:i1 + 1][d < r] = val
# owner[j,i]: -1 nobody may use; -2 free; r >= 0 reserved for rail r (its own vias)
owner = np.where(free_all, -2, -1).astype(np.int16)
rail_id = {r: k for k, r in enumerate(RAILS)}
for t in cu["traces"]:
    if t["layer"] != "inner2": continue
    for a, b in zip(t["pts"], t["pts"][1:]):
        stamp_seg(owner, a, b, t["w"] / 2 + CLR, -1)
for v in cu["vias"]:
    if v["net"] not in rail_id: stamp_disc(owner, v["x"], v["y"], v["d"] / 2 + CLR, -1)
seeds = {r: [] for r in RAILS}
for v in cu["vias"]:
    if v["net"] in rail_id:
        k = rail_id[v["net"]]; stamp_disc(owner, v["x"], v["y"], v["d"] / 2 + 0.05, k)
        seeds[v["net"]].append((int(round((v["y"] - Y0) / P)), int(round((v["x"] - X0) / P))))
# corridors: for each rail join its via clusters with shortest paths through free cells (Dijkstra on 8-grid),
# claiming a band of CORR mm around each path
CORR = 0.45
def components(cells):
    cells = list(set(cells)); comp = []; seen = set()
    for c in cells:
        if c in seen: continue
        st = [c]; seen.add(c); grp = [c]
        while st:
            a = st.pop()
            for b in cells:
                if b not in seen and abs(a[0] - b[0]) <= 14 and abs(a[1] - b[1]) <= 14:
                    seen.add(b); st.append(b); grp.append(b)
        comp.append(grp)
    return comp
def dijkstra(k, src, dst_mask):
    dist = {}; pq = []
    for s in src: dist[s] = 0.0; heapq.heappush(pq, (0.0, s, None))
    prev = {}
    while pq:
        d, c, p = heapq.heappop(pq)
        if d > dist.get(c, 1e18) + 1e-9: continue
        if p is not None: prev[c] = p
        if dst_mask[c]:
            path = [c]
            while path[-1] in prev: path.append(prev[path[-1]])
            return path
        j, i = c
        for dj in (-1, 0, 1):
            for di in (-1, 0, 1):
                if not dj and not di: continue
                jj, ii = j + dj, i + di
                if jj < 0 or ii < 0 or jj >= NY or ii >= NX: continue
                o = owner[jj, ii]
                if o == -1 or (o >= 0 and o != k): continue
                nd = d + (1.414 if dj and di else 1.0) * (0.6 if o == k else 1.0)
                if nd < dist.get((jj, ii), 1e18): dist[(jj, ii)] = nd; heapq.heappush(pq, (nd, (jj, ii), c))
    return None
unjoined = {}
for r in sorted(RAILS, key=lambda r: len(seeds[r])):
    k = rail_id[r]
    comps = components(seeds[r])
    if len(comps) <= 1: continue
    joined = set(comps[0]); rest = comps[1:]
    while rest:
        mask = np.zeros((NY, NX), bool)
        for grp in rest:
            for c in grp: mask[c] = True
        path = dijkstra(k, list(joined), mask)
        if not path: unjoined[r] = len(rest); break
        hit = next(g for g in rest if any(mask[c] and c in set(g) for c in path[:1]))
        for (j, i) in path:  # claim a corridor around the path where still free
            x, y = X0 + i * P, Y0 + j * P
            jr = int(CORR / P)
            sub = owner[max(0, j - jr):j + jr + 1, max(0, i - jr):i + jr + 1]
            sel = (sub == -2) & (np.hypot(XX[max(0, j - jr):j + jr + 1, max(0, i - jr):i + jr + 1] - x, YY[max(0, j - jr):j + jr + 1, max(0, i - jr):i + jr + 1] - y) < CORR)
            sub[sel] = k
            if owner[j, i] == -2: owner[j, i] = k
        for c in hit: joined.add(c)
        rest.remove(hit)
        joined.update(path)
# fill: every free cell goes to the nearest claimed rail cell (multi-source BFS on the free grid)
from collections import deque
q = deque()
for j, i in zip(*np.nonzero(owner >= 0)): q.append((j, i))
while q:
    j, i = q.popleft(); k = owner[j, i]
    for dj, di in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        jj, ii = j + dj, i + di
        if 0 <= jj < NY and 0 <= ii < NX and owner[jj, ii] == -2:
            owner[jj, ii] = k; q.append((jj, ii))
# polygons per rail, separated, then exact clearances to foreign copper
def raster_poly(mask):
    rects = []
    for j in range(NY):
        row = mask[j]
        if not row.any(): continue
        idx = np.flatnonzero(np.diff(np.concatenate(([0], row.view(np.int8), [0]))))
        for a, b in zip(idx[::2], idx[1::2]):
            rects.append(box(X0 + (a - 0.5) * P, Y0 + (j - 0.5) * P, X0 + (b - 0.5) * P, Y0 + (j + 0.5) * P))
    return unary_union(rects)
inner2_traces = [(t, LineString([(p["x"], p["y"]) for p in t["pts"]])) for t in cu["traces"] if t["layer"] == "inner2"]
report = {}
for r in RAILS:
    k = rail_id[r]
    g = raster_poly(owner == k).buffer(-SPLIT / 2, join_style=2).buffer(0)
    g = g.intersection(outline)
    g = g.difference(unary_union([via_disc(v, CLR) for v in cu["vias"] if v["net"] != r] +
                                  [ls.buffer(t["w"] / 2 + CLR) for t, ls in inner2_traces if t["net"] != r]))
    g = g.buffer(0)
    # the island must touch each of the rail's vias
    parts = list(g.geoms) if isinstance(g, MultiPolygon) else [g]
    vs = [Point(v["x"], v["y"]) for v in cu["vias"] if v["net"] == r]
    holding = [p for p in parts if any(p.contains(v) for v in vs)]
    covered = sum(1 for v in vs if any(p.contains(v) for p in holding))
    report[r] = dict(vias=len(vs), covered=covered, pieces=len(holding), area=round(sum(p.area for p in holding), 1), unjoined=unjoined.get(r, 0))
    for p in holding: emit("inner2", r, p)
json.dump(out, open(D + "/planes.json", "w"))
for r, v in report.items(): print(r, v)
print("pours", len(out))
