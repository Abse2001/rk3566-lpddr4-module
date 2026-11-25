import json, os, sys
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(__file__))
D = os.path.dirname(os.path.abspath(__file__))
import importlib.util
place = json.load(open(D + "/placement.json")); net = json.load(open(D + "/netlist.json")); fp = json.load(open(D + "/footprints.json"))
comps = {c["ref"]: c for c in net["components"]}
S = 22; X0, Y1 = -4, 4
W, H = int(41 * S), int(56 * S)
im = Image.new("RGB", (W * 2 + 20, H), "white"); d = ImageDraw.Draw(im)
T = lambda x, y, o=0: (o + (x - X0) * S, (Y1 - y) * S)
import math
for k, side in enumerate(("top", "bottom")):
    o = k * (W + 20)
    d.rectangle([T(-3.5, 3.5, o), T(36.5, -51.5, o)], outline=(0, 0, 0), width=2)
    for h in [(0, 0), (33, 0), (0, -48), (33, -48)]:
        x, y = T(*h, o); d.ellipse([x - 1.35 * S, y - 1.35 * S, x + 1.35 * S, y + 1.35 * S], outline=(0, 0, 0))
    d.text((o + 10, 10), side, fill=(0, 0, 0))
    for ref, pl in place.items():
        if pl["layer"] != side: continue
        role = comps[ref]["role"]
        for p in fp[role]["pads"]:
            x, y = p["x"], p["y"]
            if side == "bottom": x = -x
            a = math.radians(pl.get("rot", 0)); X = pl["x"] + x * math.cos(a) - y * math.sin(a); Y = pl["y"] + x * math.sin(a) + y * math.cos(a)
            w, h = (p["w"], p["h"]) if pl.get("rot", 0) % 180 == 0 else (p["h"], p["w"])
            col = (200, 60, 60) if side == "top" else (60, 90, 200)
            d.rectangle([T(X - w / 2, Y + h / 2, o), T(X + w / 2, Y - h / 2, o)], fill=col)
        if role not in ("RK3566", "LPDDR4", "EMMC", "DF40_HEADER"):
            d.text(T(pl["x"] + 0.3, pl["y"] + 0.6, o), ref, fill=(0, 0, 0))
im.save(sys.argv[1] if len(sys.argv) > 1 else "/tmp/claude-0/-home-user/b9d79f2d-030e-532c-84b5-c3a79e3230d3/scratchpad/place.png")
