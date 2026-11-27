# Finds the VCC_DDR copper pieces (outer-layer traces + vias + pads, not the inner2 plane) and lists the pads
# on each piece, to see which pieces carry only LPDDR4X VDDQ / RK3566 DDRPHY_VDDQL loads.
import json, os, sys
from shapely.geometry import Point, LineString, box
S = os.path.dirname(os.path.abspath(__file__)) + "/.."
pads = json.load(open(S + "/design/pads.json"))["pads"]
cu = json.load(open(os.environ.get("COPPER", S + "/route/final/copper.json")))
NET = "VCC_DDR"
VDDQ = {"B3","B5","B8","B10","D1","D5","D8","D12","F3","F10","U3","U10","W1","W5","W8","W12","AA3","AA5","AA8","AA10"}
VDDQL = {"1E6","1E7","1E9","1F5","1G5"}
def pg(p): return Point(p["x"], p["y"]).buffer(p["w"]/2, 12) if p["shape"] == "circle" else box(p["x"]-p["w"]/2, p["y"]-p["h"]/2, p["x"]+p["w"]/2, p["y"]+p["h"]/2)
items = []  # (kind, layer-set, geom, info)
for p in pads:
    if p["net"] == NET: items.append(("pad", {p["layer"]}, pg(p), p))
for t in cu["traces"]:
    if t["net"] == NET and len(t["pts"]) > 1 and t["layer"] in ("top", "bottom"):
        items.append(("trace", {t["layer"]}, LineString([(q["x"], q["y"]) for q in t["pts"]]).buffer(t["w"]/2), t))
for v in cu["vias"]:
    if v["net"] == NET: items.append(("via", {"top", "bottom"}, Point(v["x"], v["y"]).buffer(v["d"]/2), v))
n = len(items); par = list(range(n))
def f(i):
    while par[i] != i: par[i] = par[par[i]]; i = par[i]
    return i
for i in range(n):
    for j in range(i+1, n):
        if items[i][1] & items[j][1] and items[i][2].distance(items[j][2]) < 1e-4: par[f(i)] = f(j)
comp = {}
for i in range(n): comp.setdefault(f(i), []).append(i)
out = []
for k, ids in comp.items():
    ps = [items[i][3] for i in ids if items[i][0] == "pad"]
    vias = [items[i][3] for i in ids if items[i][0] == "via"]
    tags = []
    for p in ps:
        nm = p["names"][0] if p["names"] else "?"
        cls = "Q" if (p["ref"] == "U2" and set(p["names"]) & VDDQ) or (p["ref"] == "U1" and set(p["names"]) & VDDQL) else ("D" if p["ref"] in ("U1", "U2") else "P")
        tags.append((p["ref"], nm, cls))
    out.append({"pads": tags, "vias": [(v["x"], v["y"]) for v in vias], "ntraces": sum(1 for i in ids if items[i][0] == "trace")})
json.dump(out, open(S + "/costdown/vcc_ddr_pieces.json", "w"), indent=0)
mixed = [o for o in out if {t[2] for t in o["pads"]} >= {"Q", "D"}]
qonly = [o for o in out if any(t[2] == "Q" for t in o["pads"]) and not any(t[2] == "D" for t in o["pads"])]
print("pieces", len(out), "Q-only", len(qonly), "mixed", len(mixed))
for o in mixed: print("MIXED", o["pads"], len(o["vias"]), "vias")
for o in qonly: print("Q", [t for t in o["pads"]], len(o["vias"]), "vias")
