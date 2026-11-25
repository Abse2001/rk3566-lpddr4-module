# Places every component of the RK3566 module. Output: source/design/placement.json
# Frame: the Raspberry Pi CM4 carrier footprint (y up). Board 40 x 55 mm, x -3.5..36.5, y -51.5..3.5,
# M2.5 holes at (0,0) (33,0) (0,-48) (33,-48); CM4 pins 1-100 (J1) and 101-200 (J2) on the bottom.
# Big parts are placed by hand around the fixed, routed DDR block; every passive is then placed greedily as
# close as possible to the pin it serves (its anchor), on its preferred side, without overlapping anything.
import json, math, os
from shapely.geometry import box, Point, LineString
from shapely.ops import unary_union
from shapely.affinity import rotate as srot, translate
D = os.path.dirname(os.path.abspath(__file__))
net = json.load(open(D + "/netlist.json"))
fp = json.load(open(D + "/footprints.json"))
comps = {c["ref"]: c for c in net["components"]}

BOARD = box(-3.5, -51.5, 36.5, 3.5)
HOLES = [(0, 0), (33, 0), (0, -48), (33, -48)]
RK = (15.2, -19.0)
FIXED = {
    "U1": dict(x=RK[0], y=RK[1], rot=0, layer="top"),
    "U2": dict(x=RK[0] - 4, y=RK[1] + 16.6, rot=0, layer="top"),
    "U6": dict(x=25.6, y=-4.6, rot=0, layer="top"),
    "J1": dict(x=-0.46, y=-21.5, rot=0, layer="bottom", oddSide=1),
    "J2": dict(x=33.46, y=-21.5, rot=0, layer="bottom", oddSide=1),
    "U3": dict(x=15.0, y=-37.5, rot=0, layer="top"),            # RK809, BUCK4/5 side facing the SoC
    "U5": dict(x=4.6, y=-46.6, rot=0, layer="top"),             # SY8113B 5 V -> 3.3 V
    "U4": dict(x=26.5, y=-30.6, rot=0, layer="top"),            # SYR837 VDD_CPU
    "Y1": dict(x=25.6, y=-21.4, rot=0, layer="top"),            # 24 MHz next to XIN24M/XOUT24M (RK right edge, y -21.4)
    "Y2": dict(x=21.5, y=-35.0, rot=90, layer="top"),           # 32.768 kHz next to RK809 XIN/XOUT
    "Q1": dict(x=24.0, y=-45.0, rot=0, layer="top"),
}
# inductors: next to their switch pins
PM = FIXED["U3"]
FIXED.update({
    "IND_SW1": dict(x=PM["x"] - 6.3, y=PM["y"] - 1.5, rot=90, layer="top"),
    "IND_SW2": dict(x=PM["x"] - 6.3, y=PM["y"] + 2.6, rot=90, layer="top"),
    "IND_SW3": dict(x=PM["x"] - 0.3, y=PM["y"] - 6.4, rot=0, layer="top"),
    "IND_SW4": dict(x=PM["x"] - 2.2, y=PM["y"] + 6.2, rot=0, layer="top"),
    "IND_SW5": dict(x=PM["x"] + 3.2, y=PM["y"] + 6.2, rot=0, layer="top"),
    "IND_SW_CPU": dict(x=26.5, y=-26.6, rot=0, layer="top"),
    "IND_SW_3V3": dict(x=4.0, y=-41.6, rot=0, layer="top"),
})
ind_by_net = {}
for c in net["components"]:
    if c["ref"].startswith("L"):
        sw = c["pins"]["1"]
        ind_by_net[c["ref"]] = "IND_" + sw
        FIXED[c["ref"]] = FIXED.pop("IND_" + sw)

def outline(ref, pl):
    """courtyard of a placed part (pad box grown by 0.15 mm, or the package body for the big parts)"""
    role = comps[ref]["role"]
    bx = fp[role]["padBox"]
    body = {"RK3566": (7.8, 7.25), "LPDDR4": (7.5, 5.0), "EMMC": (5.75, 6.5), "RK809": (3.6, 3.6)}.get(role)
    cy = fp[role].get("court") or [bx[0] - 0.15, bx[1] - 0.15, bx[2] + 0.15, bx[3] + 0.15]
    g = box(min(cy[0], bx[0] - 0.1), min(cy[1], bx[1] - 0.1), max(cy[2], bx[2] + 0.1), max(cy[3], bx[3] + 0.1))
    if body: g = g.union(box(-body[0], -body[1], body[0], body[1])).envelope
    g = srot(g, pl.get("rot", 0), origin=(0, 0))
    return translate(g, pl["x"], pl["y"])

place = dict(FIXED)
occ = {"top": [], "bottom": []}
fixed_shapes = []
for ref, pl in place.items():
    o = outline(ref, pl)
    for r2, l2, o2 in fixed_shapes:
        if l2 == pl["layer"] and o.intersects(o2) and {ref, r2} != {"J1", "J2"}:
            raise SystemExit(f"fixed parts overlap: {ref} {r2}")
    fixed_shapes.append((ref, pl["layer"], o))
    if ref in ("J1", "J2"):
        o = box(pl["x"] - 2.0, pl["y"] - 11.1, pl["x"] + 2.0, pl["y"] + 11.1)
    occ[pl["layer"]].append(o)
# keep-outs: holes (screw heads) on both sides, board edge
keep = unary_union([Point(h).buffer(2.6) for h in HOLES] + [BOARD.exterior.buffer(0.45)])
# bottom: the routed DDR copper (traces/vias) and the RK/LPDDR4 ball fields' via fanout stay free of parts
ddr = json.load(open(D + "/../route/ddr.lane.routed.json"))
pwr = json.load(open(D + "/../route/power.fanout.json"))
bot = []
for t in ddr["traces"] + pwr:
    r = t["route"]
    for a, b in zip(r, r[1:]):
        if a["route_type"] == "wire" and b["route_type"] == "wire" and a["layer"] == b["layer"] == "bottom":
            bot.append(LineString([(a["x"] + RK[0], a["y"] + RK[1]), (b["x"] + RK[0], b["y"] + RK[1])]).buffer(0.5))
    for p in r:
        if p["route_type"] == "via":
            bot.append(Point(p["x"] + RK[0], p["y"] + RK[1]).buffer(0.6))
bottom_block = unary_union(bot + [box(RK[0] - 7.6, RK[1] - 7.0, RK[0] + 7.6, RK[1] + 7.0),
                                   box(RK[0] - 4 - 7.0, RK[1] + 16.6 - 4.6, RK[0] - 4 + 7.0, RK[1] + 16.6 + 4.6)])

def pin_xy(ref, pinname):
    """board position of a named pin of a placed part"""
    pl = place[ref]; role = comps[ref]["role"]
    for p in fp[role]["pads"]:
        if pinname in p["names"]:
            x, y = p["x"], p["y"]
            if pl["layer"] == "bottom": x = -x
            a = math.radians(pl.get("rot", 0))
            return (pl["x"] + x * math.cos(a) - y * math.sin(a), pl["y"] + x * math.sin(a) + y * math.cos(a))
    return None

# RK3566 ball positions for decoupling anchors
bxy = json.load(open(D + "/rk3566-ballxy.json"))
balls_of = {}
for b, n in comps["U1"]["pins"].items():
    if n: balls_of.setdefault(n, []).append((bxy[b][0] + RK[0], bxy[b][1] + RK[1]))

def anchor(c):
    """where a passive wants to be, and on which side"""
    nets = [n for n in c["pins"].values() if n and n != "GND"]
    g = c["group"]
    # prefer the IC pin that shares a net with this part
    for ref in ("U3", "U4", "U5", "U6", "Y1", "Y2", "Q1", "U2"):
        for n in nets:
            for pn, pnet in comps[ref]["pins"].items():
                if pnet == n and ref != "U1":
                    xy = pin_xy(ref, pn)
                    if xy and (g in ("pmic", "cpu", "sys", "emmc", "clock") or ref in ("Q1", "U2")):
                        return xy, "top" if g in ("pmic", "cpu", "sys", "clock", "io") else "bottom"
    for n in nets:
        if n in balls_of:
            pts = balls_of[n]
            return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)), "bottom"
    for n in nets:  # connector pins
        for J in ("J1", "J2"):
            for pn, pnet in comps[J]["pins"].items():
                if pnet == n:
                    return pin_xy(J, pn), "top"
    return (RK[0], RK[1] - 10), "top"

order = sorted([c for c in net["components"] if c["ref"] not in place], key=lambda c: (c["group"] != "clock", c["group"] != "pmic", c["ref"]))
failed = []
for c in order:
    (ax, ay), side = anchor(c)
    best = None
    for s in (side, "top" if side == "bottom" else "bottom"):
        for rad in [i * 0.25 for i in range(0, 80)]:
            n = max(1, int(2 * math.pi * rad / 0.3))
            for k in range(n):
                a = 2 * math.pi * k / n
                for rot in (0, 90):
                    pl = dict(x=round(ax + rad * math.cos(a), 3), y=round(ay + rad * math.sin(a), 3), rot=rot, layer=s)
                    o = outline(c["ref"], pl)
                    if not BOARD.contains(o) or o.intersects(keep): continue
                    if s == "bottom" and o.intersects(bottom_block): continue
                    if any(o.buffer(0.02).intersects(q) for q in occ[s]): continue
                    best = pl; break
                if best: break
            if best: break
        if best: break
    if not best:
        failed.append(c["ref"]); continue
    place[c["ref"]] = best
    occ[best["layer"]].append(outline(c["ref"], best))
# schematic positions: a plain grid (the schematic is a reference view; the netlist is design/netlist.json)
for i, k in enumerate(sorted(place)):
    place[k]["schX"] = (i % 20) * 6; place[k]["schY"] = -(i // 20) * 6
json.dump(place, open(D + "/placement.json", "w"), indent=0)
from collections import Counter
print("placed", len(place), "of", len(comps), Counter(p["layer"] for p in place.values()), "failed", failed)
