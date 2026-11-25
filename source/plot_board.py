# Draws the module: placement pads, routed copper per layer, conflict spots. usage: plot_board.py copper.json routes.json out.png [layers]
import json, sys, os, math
from PIL import Image, ImageDraw
D = os.path.dirname(os.path.abspath(__file__))
cu = json.load(open(sys.argv[1])); rt = json.load(open(sys.argv[2])) if len(sys.argv) > 2 and os.path.exists(sys.argv[2]) else {}
pads = json.load(open(D + "/design/pads.json"))["pads"]
show = (sys.argv[4] if len(sys.argv) > 4 else "top,inner3,bottom,inner2").split(",")
S = 24; X0, Y1 = -4, 4; W, H = int(41 * S), int(56 * S)
im = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(im)
T = lambda x, y: ((x - X0) * S, (Y1 - y) * S)
COL = {"top": (220, 40, 40), "inner3": (40, 160, 60), "bottom": (40, 90, 220), "inner2": (230, 150, 0)}
d.rectangle([T(-3.5, 3.5), T(36.5, -51.5)], outline=(0, 0, 0), width=2)
for p in pads:
    c = (235, 190, 190) if p["layer"] == "top" else (190, 200, 240)
    d.rectangle([T(p["x"] - p["w"] / 2, p["y"] + p["h"] / 2), T(p["x"] + p["w"] / 2, p["y"] - p["h"] / 2)], fill=c)
for l in ["bottom", "inner2", "inner3", "top"]:
    if l not in show: continue
    for t in cu["traces"]:
        if t["layer"] != l: continue
        d.line([T(q["x"], q["y"]) for q in t["pts"]], fill=COL[l], width=max(1, int(t["w"] * S)))
for v in cu["vias"]:
    x, y = T(v["x"], v["y"]); r = v["d"] / 2 * S; d.ellipse([x - r, y - r, x + r, y + r], outline=(0, 0, 0))
for sx, sy, l, n in rt.get("spots", []):
    x, y = T(sx, sy); d.ellipse([x - 3, y - 3, x + 3, y + 3], fill=(255, 0, 255))
im.save(sys.argv[3])
