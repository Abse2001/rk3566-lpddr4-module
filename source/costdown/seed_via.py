# Finds a spot for a lone rail via inside its inner2 island, >= C mm from all other-net copper on every layer
# (0.275 = JLC's 0.2 mm hole-to-copper for a 0.15 mm hole), nearest to a target point; adds it to COPPER.
import json, os, sys, math
import numpy as np, shapely
from shapely.geometry import Point, LineString, box, Polygon
from shapely.ops import unary_union
S = os.path.dirname(os.path.abspath(__file__)) + "/.."
F, NET, tx, ty = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4]); C = float(os.environ.get("C", 0.275))
cu = json.load(open(F + "/copper.json")); pl = json.load(open(F + "/planes.json")); P = json.load(open(S + "/design/pads.json"))
isl = unary_union([Polygon([(a["x"], a["y"]) for a in q["outer"]], [[(a["x"], a["y"]) for a in h] for h in q["holes"]]).buffer(0) for q in pl if q["layer"] == "inner2" and q["net"] == NET])
win = box(tx - 4, ty - 4, tx + 4, ty + 4)
obs = [Point(p["x"], p["y"]).buffer(p["w"] / 2) if p["shape"] == "circle" else box(p["x"] - p["w"] / 2, p["y"] - p["h"] / 2, p["x"] + p["w"] / 2, p["y"] + p["h"] / 2) for p in P["pads"] if p["net"] != NET]
obs += [LineString([(a["x"], a["y"]) for a in t["pts"]]).buffer(t["w"] / 2) for t in cu["traces"] if t["net"] != NET and len(t["pts"]) > 1]
obs += [Point(v["x"], v["y"]).buffer(v["d"] / 2) for v in cu["vias"] + P["footprintVias"] if v.get("net", "GND") != NET]
u = unary_union([g for g in obs if g.intersects(win)])
xs = np.arange(tx - 4, tx + 4, 0.025); ys = np.arange(ty - 4, ty + 4, 0.025); X, Y = np.meshgrid(xs, ys)
oth = unary_union([Polygon([(a["x"], a["y"]) for a in q["outer"]]).buffer(0) for q in pl if q["layer"] == "inner2" and q["net"] != NET])
# inside its own island, or in free inner2 (planes.py then grows the island to it), never in another rail's island
ok = (Y > float(os.environ.get("YMIN", -99))) & ~shapely.contains_xy(u.buffer(C), X, Y) & (shapely.contains_xy(isl.buffer(-0.2), X, Y) | ~shapely.contains_xy(oth.buffer(0.3), X, Y))
d = np.where(ok, np.hypot(X - tx, Y - ty), 1e9); i = np.unravel_index(np.argmin(d), d.shape)
if d[i] > 1e8: sys.exit("no spot")
x, y = round(float(X[i]), 4), round(float(Y[i]), 4)
cu["vias"].append({"x": x, "y": y, "d": 0.25, "hole": 0.15, "net": NET}); json.dump(cu, open(F + "/copper.json", "w"))
print(f"seed via {NET} at ({x}, {y}), {d[i]:.2f} mm from target")
