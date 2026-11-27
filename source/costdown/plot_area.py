import json, sys, os
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from shapely.geometry import Point, LineString, box, Polygon
S = os.path.dirname(os.path.abspath(__file__)) + "/.."
F = sys.argv[1]; x0, x1, y0, y1 = map(float, sys.argv[2:6]); out = sys.argv[6]
cu = json.load(open(F + "/copper.json")); pl = json.load(open(F + "/planes.json")); pads = json.load(open(S + "/design/pads.json"))["pads"]
COL = {"VCC0V6_DDR": "red", "VCC_DDR": "orange", "GND": "#999999"}
fig, axs = plt.subplots(1, 4, figsize=(24, 7))
for ax, lay in zip(axs, ["top", "inner2", "inner3", "bottom"]):
    ax.set_title(lay); ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_aspect("equal")
    for q in pl:
        if q["layer"] == lay and q["net"] != "GND":
            g = Polygon([(a["x"], a["y"]) for a in q["outer"]], [[(a["x"], a["y"]) for a in h] for h in q["holes"]])
            if g.intersects(box(x0, y0, x1, y1)):
                xs, ys = g.exterior.xy; ax.fill(xs, ys, color=COL.get(q["net"], "#88c"), alpha=0.35, lw=0)
    for t in cu["traces"]:
        if t["layer"] == lay and len(t["pts"]) > 1:
            ax.plot([p["x"] for p in t["pts"]], [p["y"] for p in t["pts"]], color=COL.get(t["net"], "blue"), lw=max(0.5, t["w"] * 30), alpha=0.8)
    for p in pads:
        if p["layer"] == lay and x0 - 1 < p["x"] < x1 + 1 and y0 - 1 < p["y"] < y1 + 1:
            ax.add_patch(plt.Circle((p["x"], p["y"]), p["w"] / 2, color=COL.get(p["net"], "green"), alpha=0.6) if p["shape"] == "circle" else plt.Rectangle((p["x"] - p["w"] / 2, p["y"] - p["h"] / 2), p["w"], p["h"], color=COL.get(p["net"], "green"), alpha=0.6))
            if lay == "bottom" and p["shape"] != "circle": ax.text(p["x"], p["y"], p["ref"], fontsize=6)
    for v in cu["vias"]:
        if x0 - 1 < v["x"] < x1 + 1 and y0 - 1 < v["y"] < y1 + 1:
            ax.add_patch(plt.Circle((v["x"], v["y"]), v["d"] / 2, fill=False, color=COL.get(v["net"], "black"), lw=1.2))
plt.tight_layout(); plt.savefig(out, dpi=110)
