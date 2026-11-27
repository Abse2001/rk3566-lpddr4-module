# Renames the routed copper of pads whose net changed (VCC_DDR -> VCC0V6_DDR): flood from each such pad through
# same-old-net copper on outer layers + vias, rename what it reaches. Stops if a piece also reaches a pad that keeps
# the old net (that would need a re-route instead). Usage: IN=copper.json OUT=... OLD=VCC_DDR NEW=VCC0V6_DDR
import json, os
from shapely.geometry import Point, LineString, box
S = os.path.dirname(os.path.abspath(__file__)) + "/.."
OLD, NEW = os.environ.get("OLD", "VCC_DDR"), os.environ.get("NEW", "VCC0V6_DDR")
cu = json.load(open(os.environ["IN"])); pads = json.load(open(S + "/design/pads.json"))["pads"]
pg = lambda p: Point(p["x"], p["y"]).buffer(p["w"]/2, 12) if p["shape"] == "circle" else box(p["x"]-p["w"]/2, p["y"]-p["h"]/2, p["x"]+p["w"]/2, p["y"]+p["h"]/2)
items = []
for p in pads:
    if p["net"] in (OLD, NEW): items.append(["pad", {p["layer"]}, pg(p), p])
for t in cu["traces"]:
    if t["net"] == OLD and len(t["pts"]) > 1: items.append(["trace", {t["layer"]}, LineString([(q["x"], q["y"]) for q in t["pts"]]).buffer(t["w"]/2), t])
for v in cu["vias"]:
    if v["net"] == OLD: items.append(["via", {"top", "inner1", "inner2", "inner3", "inner4", "bottom"}, Point(v["x"], v["y"]).buffer(v["d"]/2), v])
n = len(items); par = list(range(n))
def f(i):
    while par[i] != i: par[i] = par[par[i]]; i = par[i]
    return i
from shapely.strtree import STRtree
tree = STRtree([it[2] for it in items])
for i in range(n):
    for j in tree.query(items[i][2]):
        j = int(j)
        if j > i and items[i][1] & items[j][1] and items[i][2].distance(items[j][2]) < 1e-4: par[f(i)] = f(j)
groups = {}
for i in range(n): groups.setdefault(f(i), []).append(i)
nt = nv = 0; bad = []
for g in groups.values():
    nets = {items[i][3]["net"] for i in g if items[i][0] == "pad"}
    if NEW not in nets: continue
    if OLD in nets: bad.append([items[i][3]["ref"] + "." + items[i][3]["names"][0] for i in g if items[i][0] == "pad"]); continue
    for i in g:
        if items[i][0] == "trace": items[i][3]["net"] = NEW; nt += 1
        if items[i][0] == "via": items[i][3]["net"] = NEW; nv += 1
print(f"renamed {nt} traces, {nv} vias to {NEW}; mixed pieces: {bad}")
json.dump(cu, open(os.environ["OUT"], "w"))
