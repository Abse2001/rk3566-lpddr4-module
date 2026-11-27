# Places parts that are in netlist.json but not yet in placement.json (ECO placement: every placed part and all
# routed copper stay where they are). Each new part goes to the free spot nearest its target that:
#   - keeps JLCPCB's SMD spacing table to every part on its side (place.py's extent/kind rules),
#   - does not overlap any courtyard on its side (place.py's outline),
#   - keeps its pads CLR mm from all copper on its side (pads, traces, vias; vias count on both sides),
#   - stays 0.3 mm inside the board edge and clear of the mounting holes.
# Usage: COPPER=route/final/copper.json python3 costdown/place_new.py   (targets below; writes design/placement.json)
import json, math, os, sys
from shapely.geometry import box, Point, LineString
from shapely.ops import unary_union
from shapely.affinity import rotate as srot, translate
S = os.path.dirname(os.path.abspath(__file__)) + "/.."
net = json.load(open(S + "/design/netlist.json")); fp = json.load(open(S + "/design/footprints.json"))
place = json.load(open(S + "/design/placement.json"))
P = json.load(open(S + "/design/pads.json")); pads, fvias = P["pads"], P["footprintVias"]
cu = json.load(open(os.environ.get("COPPER", S + "/route/final/copper.json")))
comps = {c["ref"]: c for c in net["components"]}
CLR = float(os.environ.get("CLR", 0.2))
BOARD = box(-3.5, -51.5, 36.5, 3.5).buffer(-0.3)
HOLES = unary_union([Point(h).buffer(1.35 + 0.5) for h in [(0, 0), (33, 0), (0, -48), (33, -48)]])
KIND = {"RK3566": "BGA", "LPDDR4": "BGA", "EMMC": "BGA", "BUCK_CPU": "BGA", "RK809": "QFN", "BUCK_3V3": "SOT",
        "NMOS_DUAL": "SOT", "DF40_HEADER": "CONN", "LDO_VDDQ": "SOT"}
JLC = {("chip", "chip"): 0.15, ("chip", "BGA"): 1.0, ("chip", "QFN"): 1.0, ("chip", "SOT"): 0.2, ("BGA", "BGA"): 2.0,
       ("BGA", "QFN"): 1.5, ("BGA", "SOT"): 1.0, ("QFN", "SOT"): 1.0, ("QFN", "QFN"): 1.0, ("SOT", "SOT"): 0.2}
jlc = lambda a, b: JLC.get((a, b), JLC.get((b, a), 0.3))
kind = lambda r: KIND.get(comps[r]["role"], "chip")
BODY_OUT = {"RK3566": (7.8, 7.25), "LPDDR4": (7.5, 5.0), "EMMC": (5.75, 6.5), "RK809": (3.6, 3.6)}
BODY_EXT = {"RK809": (3.6, 3.6), "BUCK_CPU": (1.0, 0.8), "BUCK_3V3": (1.45, 0.8), "NMOS_DUAL": (1.0, 0.625),
            "XTAL_24M": (1.25, 1.0), "XTAL_32K": (1.6, 0.75), "L_470N": (1.25, 1.0), "L_CPU": (1.25, 1.0),
            "L_3V3": (2.0, 2.0), "LDO_VDDQ": (1.5, 0.85)}
def outline(r, pl):
    role = comps[r]["role"]; bx = fp[role]["padBox"]; body = BODY_OUT.get(role)
    cy = {"BUCK_CPU": [-1.25, -1.05, 1.25, 1.05]}.get(role) or fp[role].get("court") or [bx[0] - .15, bx[1] - .15, bx[2] + .15, bx[3] + .15]
    g = box(min(cy[0], bx[0] - .1), min(cy[1], bx[1] - .1), max(cy[2], bx[2] + .1), max(cy[3], bx[3] + .1))
    if body: g = g.union(box(-body[0], -body[1], body[0], body[1])).envelope
    return translate(srot(g, pl.get("rot", 0), origin=(0, 0)), pl["x"], pl["y"])
def extent(r, pl):
    role = comps[r]["role"]; g = box(*fp[role]["padBox"]); body = BODY_EXT.get(role)
    if body: g = g.union(box(-body[0], -body[1], body[0], body[1]))
    return translate(srot(g, pl.get("rot", 0), origin=(0, 0)), pl["x"], pl["y"])
def padgeoms(r, pl):
    out = []
    for p in fp[comps[r]["role"]]["pads"]:
        x = -p["x"] if pl["layer"] == "bottom" else p["x"]
        g = Point(x, p["y"]).buffer(p["w"] / 2, 12) if p["shape"] == "circle" else box(x - p["w"] / 2, p["y"] - p["h"] / 2, x + p["w"] / 2, p["y"] + p["h"] / 2)
        out.append((p["names"], translate(srot(g, pl.get("rot", 0), origin=(0, 0)), pl["x"], pl["y"])))
    return out
# copper per side
cop = {"top": [], "bottom": []}
for p in pads:
    g = Point(p["x"], p["y"]).buffer(p["w"] / 2, 12) if p["shape"] == "circle" else box(p["x"] - p["w"] / 2, p["y"] - p["h"] / 2, p["x"] + p["w"] / 2, p["y"] + p["h"] / 2)
    cop[p["layer"]].append(g)
for t in cu["traces"]:
    if t["layer"] in cop and len(t["pts"]) > 1:
        cop[t["layer"]].append(LineString([(q["x"], q["y"]) for q in t["pts"]]).buffer(t["w"] / 2))
for v in cu["vias"] + fvias:
    g = Point(v["x"], v["y"]).buffer(v["d"] / 2, 12); cop["top"].append(g); cop["bottom"].append(g)
cop = {k: unary_union(v) for k, v in cop.items()}
occ = {"top": [], "bottom": []}; ext = {"top": [], "bottom": []}
for r, pl in place.items():
    if r not in comps: continue
    o = outline(r, pl)
    if r in ("J1", "J2"): o = box(pl["x"] - 2.0, pl["y"] - 11.1, pl["x"] + 2.0, pl["y"] + 11.1)
    occ[pl["layer"]].append(o); ext[pl["layer"]].append((r, kind(r), extent(r, pl)))
def pad_xy(r, name):
    for p in pads:
        if p["ref"] == r and name in p["names"]: return p["x"], p["y"]
    pl = place[r]
    for names, g in padgeoms(r, pl):
        if name in names: return g.centroid.x, g.centroid.y
    raise KeyError((r, name))
def try_place(r, target, layers, rmax=float(os.environ.get("RMAX", 10)), step=float(os.environ.get("STEP", 0.1))):
    tx, ty = target; best = None
    n = int(rmax / step)
    cands = sorted(((i * step, j * step) for i in range(-n, n + 1) for j in range(-n, n + 1) if (i * i + j * j) * step * step <= rmax * rmax), key=lambda d: math.hypot(*d))
    for dx, dy in cands:
        for lay in layers:
            for rot in (0, 90, 180, 270):
                pl = {"x": round(tx + dx, 3), "y": round(ty + dy, 3), "rot": rot, "layer": lay}
                o = outline(r, pl)
                if not BOARD.contains(o) or o.intersects(HOLES): continue
                if any(o.intersects(o2) for o2 in occ[lay]): continue
                e = extent(r, pl)
                if any(e.distance(e2) < jlc(kind(r), k2) - 1e-6 for _, k2, e2 in ext[lay]): continue
                if any(cop[lay].distance(g) < CLR for _, g in padgeoms(r, pl)): continue
                return pl
    return None
PLAN = json.loads(os.environ["PLAN"]) if os.environ.get("PLAN") else None
new = [r for r in comps if r not in place]
print("new parts:", new)
for r, tgt, layers in PLAN:
    if isinstance(tgt, list) and isinstance(tgt[0], str): tgt = pad_xy(tgt[0], tgt[1])
    pl = try_place(r, tgt, layers)
    if not pl: print("NO SPOT", r); continue
    pl.update(schX=0, schY=0); place[r] = pl
    o = outline(r, pl); occ[pl["layer"]].append(o); ext[pl["layer"]].append((r, kind(r), extent(r, pl)))
    cop[pl["layer"]] = cop[pl["layer"]].union(unary_union([g for _, g in padgeoms(r, pl)]))
    print(f"{r:5s} {comps[r]['role']:12s} at ({pl['x']:.2f}, {pl['y']:.2f}) rot {pl['rot']} {pl['layer']}, {math.hypot(pl['x'] - tgt[0], pl['y'] - tgt[1]):.2f} mm from target")
missing = [r for r in comps if r not in place]
if missing: print("UNPLACED", missing)
json.dump(place, open(S + "/design/placement.json", "w"), indent=0)
