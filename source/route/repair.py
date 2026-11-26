# Clearance repair after routing: a trace that misses the 0.1 mm clearance to another net's copper by a small amount
# (grid rounding, or a few cells the negotiation left) is moved locally: the vertices near the contact are shifted
# straight away from the obstacle by the missing distance (plus a margin). The move is kept only if the moved trace
# clears all copper of other nets by GAP on its layer (pads, traces, vias), so a repair never creates a violation.
# Usage: COPPER=copper.json [MAX=0.03] python3 repair.py   (rewrites COPPER in place, prints what it moved)
import json, os, math
from shapely.geometry import Point, LineString, box
from shapely.strtree import STRtree
D = os.path.dirname(os.path.abspath(__file__))
CP = os.environ.get("COPPER", D + "/copper.json")
cu = json.load(open(CP))
pads = json.load(open(D + "/../design/pads.json"))
GAP, MAX, MARGIN, REACH = 0.1, float(os.environ.get("MAX", 0.03)), 0.004, 0.45
fv = [dict(v, net="GND") for v in pads["footprintVias"]]

def obstacles(layer):
    """(geometry, net) of all copper on a layer: pads, traces (per segment), every via"""
    out = []
    for p in pads["pads"]:
        if p["layer"] != layer: continue
        g = Point(p["x"], p["y"]).buffer(p["w"] / 2, 24) if p["shape"] == "circle" else box(p["x"] - p["w"] / 2, p["y"] - p["h"] / 2, p["x"] + p["w"] / 2, p["y"] + p["h"] / 2)
        out.append((g, p["net"], None))
    for k, t in enumerate(cu["traces"]):
        if t["layer"] != layer: continue
        for a, b in zip(t["pts"], t["pts"][1:]):
            out.append((LineString([(a["x"], a["y"]), (b["x"], b["y"])]).buffer(t["w"] / 2, 8), t["net"], k))
    for v in cu["vias"] + fv:
        # a via counts with its hole rule (0.2 mm hole to copper): grown so the 0.1 mm gap check covers it
        out.append((Point(v["x"], v["y"]).buffer(v["d"] / 2 + max(0, 0.2 - (v["d"] - v["hole"]) / 2 - GAP), 16), v["net"], None))
    return out

from shapely.ops import nearest_points
moved = 0
for layer in sorted({t["layer"] for t in cu["traces"]}):
    obs = obstacles(layer); tree = STRtree([g for g, _, _ in obs])
    # traces on this layer that miss the clearance somewhere (by any amount)
    cand = set()
    for g, n, owner in obs:
        if owner is None: continue
        for j in tree.query(g.buffer(GAP)):
            g2, n2, o2 = obs[j]
            if n2 != n and o2 != owner and g.distance(g2) < GAP - 1e-4: cand.add(owner)
    for k in sorted(cand):
        t = cu["traces"][k]
        for attempt in range(4):
            line = LineString([(q["x"], q["y"]) for q in t["pts"]])
            geom = line.buffer(t["w"] / 2, 8)
            worst = None
            for j in tree.query(geom.buffer(GAP)):
                g, n, owner = obs[j]
                if n == t["net"] or owner == k: continue
                d = geom.distance(g)
                if d < GAP - 1e-4 and (worst is None or d < worst[0]): worst = (d, g, n)
            if worst is None: break
            d, g, n = worst
            if GAP - d > MAX: break  # not a small miss: leave it to the router (check.py reports it)
            pa, pb = nearest_points(line, g)
            dx, dy = pa.x - pb.x, pa.y - pb.y; L = math.hypot(dx, dy) or 1e-9
            ux, uy = dx / L, dy / L
            shift = GAP - d + MARGIN
            new = [dict(q) for q in t["pts"]]
            for q in new[1:-1] if len(new) > 2 else []:
                if math.hypot(q["x"] - pa.x, q["y"] - pa.y) < REACH:
                    q["x"] = round(q["x"] + ux * shift, 4); q["y"] = round(q["y"] + uy * shift, 4)
            ng = LineString([(q["x"], q["y"]) for q in new]).buffer(t["w"] / 2, 8)
            ok = all(n2 == t["net"] or o2 == k or ng.distance(g2) >= GAP - 1e-4 for g2, n2, o2 in (obs[j] for j in tree.query(ng.buffer(GAP))))
            if not ok: break
            print(f"moved {t['net']} on {layer} {shift:.3f} mm away from {n} at ({pa.x:.2f}, {pa.y:.2f}) (was {d:.3f} mm)")
            t["pts"] = new; moved += 1
            # refresh this trace's segments in the obstacle list
            obs = [o for o in obs if o[2] != k] + [(LineString([(a_["x"], a_["y"]), (b_["x"], b_["y"])]).buffer(t["w"] / 2, 8), t["net"], k) for a_, b_ in zip(new, new[1:])]
            tree = STRtree([g_ for g_, _, _ in obs])
json.dump(cu, open(CP, "w"))
print("repairs:", moved)
