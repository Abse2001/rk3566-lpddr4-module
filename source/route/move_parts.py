# Moves the parts that sit closer to another part than JLCPCB's SMD spacing table allows (dfm_spacing.py rules),
# by the smallest shift that satisfies every rule, keeping their rotation. A candidate position is accepted only
# if, on the part's layer:
#   - it keeps the table spacing to every other part (pads + datasheet body), with the parts moved so far,
#   - its pads clear all copper of other nets by 0.1 mm (traces, vias, other pads), so no other net needs re-routing,
#   - it stays 0.3 mm inside the board edge and clear of the mounting holes.
# The part's own connections are re-made afterwards by connect.py. Writes design/placement.json and a list of
# moved parts (route/moved.json: ref -> old/new pads) for connect.py.
# Usage: COPPER=route/final/copper.json [REFS=C1,C2] [RMAX=3] python3 route/move_parts.py
import json, os, math, itertools
from shapely.geometry import box, Point, LineString
from shapely.ops import unary_union
from shapely import affinity
D = os.path.dirname(os.path.abspath(__file__)); S = D + "/.."
pads = json.load(open(S + "/design/pads.json"))["pads"]
fvias = json.load(open(S + "/design/pads.json"))["footprintVias"]
pl = json.load(open(S + "/design/placement.json"))
net = json.load(open(S + "/design/netlist.json")); roles = json.load(open(S + "/design/roles.json"))
cu = json.load(open(os.environ.get("COPPER", D + "/copper.json")))
role = {c["ref"]: c["role"] for c in net["components"]}
fp = lambda r: roles.get(role.get(r, ""), {}).get("fp") if isinstance(roles.get(role.get(r, "")), dict) else None
BODY = {"0201": (0.6, 0.3), "0402": (1.0, 0.5), "0603": (1.6, 0.8), "0805": (2.0, 1.25), "1206": (3.2, 1.6)}
# datasheet bodies (x by y at rotation 0) of the parts whose pads do not cover the body
PBODY = {"U4": (2.0, 1.6), "U5": (2.9, 1.6), "Q1": (2.0, 1.25), "Y1": (2.5, 2.0), "Y2": (3.2, 1.5)}
for l in ("L1", "L2", "L3", "L4", "L5", "L6"): PBODY[l] = (2.0, 2.5) if pl[l]["rot"] % 180 == 90 else (2.5, 2.0)
PBODY["L7"] = (4.0, 4.0)
KIND = {"U1": "BGA", "U2": "BGA", "U6": "BGA", "U4": "BGA", "U3": "QFN", "U5": "SOT", "Q1": "SOT", "J1": "CONN", "J2": "CONN"}
RULE = {("chip", "chip"): 0.15, ("chip", "BGA"): 1.0, ("chip", "QFN"): 1.0, ("chip", "SOT"): 0.2, ("BGA", "BGA"): 2.0,
        ("BGA", "QFN"): 1.5, ("BGA", "SOT"): 1.0, ("QFN", "SOT"): 1.0}
def rule(a, b): return RULE.get((a, b), RULE.get((b, a), 0.3))
# power inductors and crystals have no row in JLCPCB's table: they count as chip parts of their size (as in place.py)
def kind(r): return KIND.get(r, "chip" if fp(r) in BODY or r[0] in "LY" else "other")
def padg(p, dx=0, dy=0):
    x, y = p["x"] + dx, p["y"] + dy
    return Point(x, y).buffer(p["w"] / 2, 16) if p["shape"] == "circle" else box(x - p["w"] / 2, y - p["h"] / 2, x + p["w"] / 2, y + p["h"] / 2)
bypad = {}
for p in pads: bypad.setdefault(p["ref"], []).append(p)
def geom(r, dx=0, dy=0):
    g = [padg(p, dx, dy) for p in bypad[r]]
    q = pl[r]; x, y = q["x"] + dx, q["y"] + dy
    if fp(r) in BODY:
        L, W = BODY[fp(r)]; g.append(affinity.translate(affinity.rotate(box(-L / 2, -W / 2, L / 2, W / 2), q.get("rot", 0)), x, y))
    elif r in PBODY:
        L, W = PBODY[r]; L, W = (W, L) if r in ("U4", "U5", "Q1", "Y1", "Y2") and q.get("rot", 0) % 180 == 90 else (L, W)
        g.append(box(x - L / 2, y - W / 2, x + L / 2, y + W / 2))
    return unary_union(g)
G = {r: geom(r) for r in bypad}
def bad_pairs():
    out = []
    for a, b in itertools.combinations(G, 2):
        if pl[a]["layer"] != pl[b]["layer"]: continue
        need = rule(kind(a), kind(b))
        if G[a].distance(G[b]) < need - 1e-6: out.append((a, b, need))
    return out
BOARD = box(-3.5, -51.5, 36.5, 3.5); HOLES = [Point(h).buffer(1.35 + 0.3) for h in [(0, 0), (33, 0), (0, -48), (33, -48)]]
INNER = BOARD.buffer(-0.3)
viol = bad_pairs()
# the part to move in each pair: the passive (the IC stays); between two passives, the one listed in REFS or the later one
movers = []
for a, b, need in viol:
    m = b if kind(a) != "chip" else a if kind(b) != "chip" else b
    if m not in movers: movers.append(m)
if os.environ.get("REFS"): movers = os.environ["REFS"].split(",")
print("parts to move:", movers)
def copper_obstacles(layer, skip_nets):
    out = []
    for t in cu["traces"]:
        if t["layer"] == layer and t["net"] not in skip_nets and len(t["pts"]) > 1:
            out.append(LineString([(q["x"], q["y"]) for q in t["pts"]]).buffer(t["w"] / 2))
    for v in cu["vias"] + [dict(v, net="GND") for v in fvias]:
        if v["net"] not in skip_nets: out.append(Point(v["x"], v["y"]).buffer(v["d"] / 2))
    return unary_union(out)
RMAX = float(os.environ.get("RMAX", 3.0)); STEP = 0.05
moved = {}
for r in movers:
    lay = pl[r]["layer"]; nets = {p["net"] for p in bypad[r]}
    # other-net copper: anything not on this part's nets (own-net copper may be crossed: connect.py re-makes it)
    obs = copper_obstacles(lay, nets)
    others = [(o, G[o]) for o in G if o != r and pl[o]["layer"] == lay]
    cands = sorted(((i * STEP, j * STEP) for i in range(-int(RMAX / STEP), int(RMAX / STEP) + 1) for j in range(-int(RMAX / STEP), int(RMAX / STEP) + 1) if (i * i + j * j) * STEP * STEP <= RMAX * RMAX), key=lambda d: math.hypot(*d))
    done = False
    for dx, dy in cands:
        g = geom(r, dx, dy)
        if not INNER.contains(g) or any(h.intersects(g) for h in HOLES): continue
        if any(g.distance(og) < rule(kind(r), kind(o)) - 1e-6 for o, og in others): continue
        pg = unary_union([padg(p, dx, dy) for p in bypad[r]])
        if obs.distance(pg) < 0.1 + 0.005: continue
        moved[r] = {"dx": round(dx, 3), "dy": round(dy, 3), "old": [dict(p) for p in bypad[r]]}
        pl[r]["x"] = round(pl[r]["x"] + dx, 4); pl[r]["y"] = round(pl[r]["y"] + dy, 4)
        for p in bypad[r]: p["x"] = round(p["x"] + dx, 4); p["y"] = round(p["y"] + dy, 4)
        G[r] = geom(r); moved[r]["new"] = [dict(p) for p in bypad[r]]
        print(f"moved {r} by ({dx:+.2f}, {dy:+.2f}) = {math.hypot(dx, dy):.2f} mm")
        done = True; break
    if not done: print(f"NO POSITION for {r} within {RMAX} mm")
left = bad_pairs(); print("pairs still below the table:", left)
json.dump(pl, open(S + "/design/placement.json", "w"), indent=1)
json.dump(moved, open(D + "/moved.json", "w"), indent=1)
