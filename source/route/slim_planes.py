# Fewer vertices in the plane outlines (the raster staircases make the circuit JSON too large to publish). Each pour
# is shrunk by T, simplified with tolerance T and rounded to 0.1 um: the result lies inside the original pour, so no
# clearance gets smaller (copper loses at most 2T at its edges). Re-run check.py afterwards (connectivity).
# Usage: PLANES=planes.json [T=0.015] [MIN_A=0.1 mm2] python3 slim_planes.py   (rewrites PLANES in place)
import json, os
from shapely.geometry import Polygon, MultiPolygon
P = os.environ["PLANES"]; T = float(os.environ.get("T", 0.015)); MIN_A = float(os.environ.get("MIN_A", 0.1))
pl = json.load(open(P)); out = []
for p in pl:
    g = Polygon([(q["x"], q["y"]) for q in p["outer"]], [[(q["x"], q["y"]) for q in h] for h in p["holes"]]).buffer(0)
    s = g.buffer(-T, join_style=2).simplify(T, preserve_topology=True)
    for part in (s.geoms if isinstance(s, MultiPolygon) else [s]):
        if part.is_empty or part.area < MIN_A: continue  # slivers: floating, too small to etch reliably
        r = lambda cs: [{"x": round(x, 4), "y": round(y, 4)} for x, y in list(cs)[:-1]]
        out.append(dict(p, outer=r(part.exterior.coords), holes=[r(h.coords) for h in part.interiors], area=round(part.area, 3)))
print(len(pl), "pours ->", len(out), "pieces;", sum(len(p["outer"]) + sum(map(len, p["holes"])) for p in pl), "->", sum(len(p["outer"]) + sum(map(len, p["holes"])) for p in out), "vertices")
json.dump(out, open(P, "w"))
