# Adds the escape stubs of escape_stubs.json to an LPDDR4 routing problem as obstacles, so the DDR solver routes
# around them: each trace segment as thin rects along it on its layer, each via as a pad on every DDR layer.
# Usage: python3 ddr_reserve.py in.json out.json
import json, sys, math, os
RK = (15.2, -19.0)
srj = json.load(open(sys.argv[1])); st = json.load(open(os.path.dirname(os.path.abspath(__file__)) + "/escape_stubs.json"))
obs = srj["obstacles"]
for t in st["traces"]:
    for a, b in zip(t["pts"], t["pts"][1:]):
        n = max(1, int(math.hypot(b["x"] - a["x"], b["y"] - a["y"]) / 0.05))
        for k in range(n + 1):
            x = a["x"] + (b["x"] - a["x"]) * k / n - RK[0]; y = a["y"] + (b["y"] - a["y"]) * k / n - RK[1]
            obs.append({"type": "rect", "layers": [t["layer"]], "center": {"x": round(x, 4), "y": round(y, 4)}, "width": t["w"], "height": t["w"], "connectedTo": [t["net"]]})
for v in st["vias"]:
    obs.append({"type": "rect", "layers": ["top", "inner1", "inner2", "inner3", "inner4", "bottom"], "center": {"x": round(v["x"] - RK[0], 4), "y": round(v["y"] - RK[1], 4)}, "width": v["d"], "height": v["d"], "connectedTo": [v["net"]]})
json.dump(srj, open(sys.argv[2], "w"))
print("obstacles", len(obs))
