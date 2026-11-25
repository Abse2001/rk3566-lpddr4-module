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
    "U3": dict(x=15.0, y=-37.5, rot=270, layer="top"),           # RK809 turned so BUCK1/2 face the SoC, BUCK4/5 face right, BUCK3 left
    "U5": dict(x=4.6, y=-46.6, rot=0, layer="top"),             # SY8113B 5 V -> 3.3 V
    "U4": dict(x=26.5, y=-30.6, rot=0, layer="top"),            # SYR837 VDD_CPU
    "Y1": dict(x=25.6, y=-21.4, rot=0, layer="top"),            # 24 MHz next to XIN24M/XOUT24M (RK right edge, y -21.4)
    "Y2": dict(x=18.2, y=-42.9, rot=0, layer="top"),            # 32.768 kHz next to RK809 XIN/XOUT (bottom side after the turn)
    "Q1": dict(x=24.0, y=-45.0, rot=0, layer="top"),
}
# inductors: next to their switch pins
PM = FIXED["U3"]
FIXED.update({
    # switch pins after the 270 degree turn: SW1 (LOGIC) and SW2 (GPU) on top, SW4 (NPU) and SW5 (1V8) on the right,
    # SW3 (DDR) on the left; each inductor next to its pin, ordered like the rail clusters under the SoC
    "IND_SW1": dict(x=PM["x"] - 2.6, y=PM["y"] + 6.0, rot=90, layer="top"),
    "IND_SW2": dict(x=PM["x"] + 1.0, y=PM["y"] + 6.0, rot=90, layer="top"),
    "IND_SW4": dict(x=PM["x"] + 6.4, y=PM["y"] + 2.4, rot=0, layer="top"),
    "IND_SW5": dict(x=PM["x"] + 6.4, y=PM["y"] - 1.6, rot=0, layer="top"),
    "IND_SW3": dict(x=PM["x"] - 6.3, y=PM["y"] + 0.4, rot=90, layer="top"),
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

# bulk decoupling of the core rails: just outside the SoC edge their regulator feed comes in from
FEED_EDGE = {"VDD_LOGIC": (13.2, -27.6), "VDD_GPU": (14.8, -27.6), "VDD_NPU": (18.5, -27.6),
             "VDD_CPU": (24.4, -17.0), "VCC_DDR": (6.6, -16.5)}
def anchor(c):
    """where a passive wants to be, and on which side"""
    nets = [n for n in c["pins"].values() if n and n != "GND"]
    g = c["group"]
    if g == "decap" and nets and nets[0] in FEED_EDGE:
        return FEED_EDGE[nets[0]], "bottom"
    # prefer the IC pin that shares a net with this part
    # regulator output capacitors belong at their inductor's output pad
    for ref in [k for k in comps if k.startswith("L")] + ["U3", "U4", "U5", "U6", "Y1", "Y2", "Q1", "U2"]:
        for n in nets:
            for pn, pnet in comps[ref]["pins"].items():
                if pnet == n and ref != "U1":
                    xy = pin_xy(ref, pn)
                    if xy and (g in ("pmic", "cpu", "sys", "emmc", "clock") or ref in ("Q1", "U2")) and ref in place:
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

# ---- decoupling under the SoC: a 0201 between a rail via and a ground via one ball pitch apart, on the bottom ----
# (the vias are the via-in-pad of the inner-grid balls, route/bga_vias.json, and the supplied fanout vias)
RV = D + "/../route/"
vias = json.load(open(RV + "fixed.json"))["vias"] + (json.load(open(RV + "bga_vias.json")) if os.path.exists(RV + "bga_vias.json") else [])
fx = json.load(open(RV + "fixed.json"))
bot_cu = [(Point(v["x"], v["y"]).buffer(v["d"] / 2), v["net"]) for v in vias]
for t in fx["traces"]:
    if t["layer"] == "bottom":
        for a2, b2 in zip(t["pts"], t["pts"][1:]):
            bot_cu.append((LineString([(a2["x"], a2["y"]), (b2["x"], b2["y"])]).buffer(t["w"] / 2), t["net"]))
from shapely.strtree import STRtree
bot_tree = STRtree([g for g, _ in bot_cu])
under = []  # placed pad shapes under the SoC
def try_cap(c):
    rail = c["pins"]["1"] if c["pins"]["2"] == "GND" else c["pins"]["2"]
    rail_pin = "1" if c["pins"]["1"] == rail else "2"
    rv = [v for v in vias if v["net"] == rail]
    gv = [v for v in vias if v["net"] == "GND"]
    cand = []
    for a in rv:
        for g in gv:
            dx, dy = g["x"] - a["x"], g["y"] - a["y"]
            if (abs(dy) < 0.02 and 0.62 < abs(dx) < 0.70) or (abs(dx) < 0.02 and 0.62 < abs(dy) < 0.70):
                cand.append((a, g))
    # nearest the rail's ball cluster first
    pts = balls_of.get(rail, [])
    cx = sum(p[0] for p in pts) / len(pts) if pts else RK[0]; cy = sum(p[1] for p in pts) / len(pts) if pts else RK[1]
    cand.sort(key=lambda ag: math.hypot(ag[0]["x"] - cx, ag[0]["y"] - cy))
    for a, g in cand:
        mx, my = (a["x"] + g["x"]) / 2, (a["y"] + g["y"]) / 2
        # bottom side mirrors x: pin1 (local -0.33) lands at +0.33 along the rotated x axis
        ang = math.degrees(math.atan2(a["y"] - my, a["x"] - mx)) if rail_pin == "1" else math.degrees(math.atan2(g["y"] - my, g["x"] - mx))
        rot = round(ang / 90) * 90 % 360
        padg = [Point(a["x"], a["y"]).buffer(0.25), Point(g["x"], g["y"]).buffer(0.25)]
        padg = [box(a["x"] - 0.23, a["y"] - 0.2, a["x"] + 0.23, a["y"] + 0.2) if rot % 180 == 0 else box(a["x"] - 0.2, a["y"] - 0.23, a["x"] + 0.2, a["y"] + 0.23),
                box(g["x"] - 0.23, g["y"] - 0.2, g["x"] + 0.23, g["y"] + 0.2) if rot % 180 == 0 else box(g["x"] - 0.2, g["y"] - 0.23, g["x"] + 0.2, g["y"] + 0.23)]
        bad = False
        for pg, pn in zip(padg, (rail, "GND")):
            for k in bot_tree.query(pg.buffer(0.1)):
                gg, kn = bot_cu[k]
                if kn != pn and gg.distance(pg) < 0.1 + 1e-6: bad = True; break
            if bad or any(q.distance(pg) < 0.12 for q in under): bad = True
            if bad: break
        if bad: continue
        under.extend(padg)
        return dict(x=round(mx, 4), y=round(my, 4), rot=rot, layer="bottom")
    return None
under_failed = []
for c in net["components"]:
    if c["ref"] in place or c["group"] != "decap" or comps[c["ref"]]["role"] not in ("C_100N_0201", "C_1U_0201"): continue
    pl = try_cap(c)
    if pl: place[c["ref"]] = pl
    else: under_failed.append(c["ref"])
print("decaps under the SoC:", sum(1 for c in net["components"] if c["ref"] in place and c["group"] == "decap"), "fell back:", under_failed)

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
