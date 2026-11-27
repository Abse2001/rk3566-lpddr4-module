# Push solver for JLCPCB's via-hole-to-copper rule (drilled hole >= HOLE mm from other-net copper on every layer).
# Instead of re-routing, each violation is fixed by a small local move:
#   - a trace passing too close to a via gets a new vertex at its closest point, pushed straight away from the hole
#     (a shallow jog around the via), or an existing vertex near that point is pushed;
#   - a routed via too close to a pad / via / trace end is moved away, its own trace ends follow it.
# A move is kept only if, around the moved copper, no copper-to-copper gap drops below GAP (0.1 mm), no hole gets
# closer than before, and the hole deficit goes down. Fixed copper never moves: the LPDDR4 block, the power-ball
# fanout, via-in-pad (fixed.json, bga_vias.json, footprint vias), DDR_* nets and every differential-pair net
# (P and N), so no length or skew changes on any matched net.
# Usage: COPPER=final/copper.json [HOLE=0.2] [ROUNDS=30] python3 push_holes.py   (rewrites COPPER in place)
import json, os, math
from shapely.geometry import Point, LineString, box
from shapely.strtree import STRtree
D = os.path.dirname(os.path.abspath(__file__))
CP = os.environ["COPPER"]; cu = json.load(open(CP))
P = json.load(open(D + "/../design/pads.json")); pads = P["pads"]
fx = json.load(open(D + "/fixed.json")); bv = json.load(open(D + "/bga_vias.json"))
HOLE, GAP, EPS = float(os.environ.get("HOLE", 0.2)), 0.1, 0.004
ROUNDS = int(os.environ.get("ROUNDS", 30)); STEP_MAX = float(os.environ.get("STEP_MAX", 0.08))
LAYERS = ["top", "inner1", "inner2", "inner3", "inner4", "bottom"]
vk = lambda v: (v["net"], round(v["x"], 3), round(v["y"], 3))
tk = lambda t: (t["net"], t["layer"], tuple((round(p["x"], 3), round(p["y"], 3)) for p in t["pts"]))
FIXV = {vk(v) for v in fx["vias"] + bv} | {vk(dict(v, net="GND")) for v in P["footprintVias"]}
FIXT = {tk(t) for t in fx["traces"]}
# differential pairs (same rule as pairs.py) never move either: a jog would change P/N skew
import re
_names = {t["net"] for t in cu["traces"]} | {v["net"] for v in cu["vias"]}
PAIR_NETS = set(); PARTNER = {}
for n in _names:
    m = re.match(r"(.*?)(P|_P|DP)(_C)?$", n or "")
    if m:
        neg = m.group(1) + {"P": "N", "_P": "_N", "DP": "DM"}[m.group(2)] + (m.group(3) or "")
        if neg in _names: PAIR_NETS |= {n, neg}; PARTNER[n] = neg; PARTNER[neg] = n
fixed_net = lambda n: n is None or n.startswith("DDR_") or n in PAIR_NETS
vias = cu["vias"] + [dict(v, net="GND", _fp=1) for v in P["footprintVias"]]
traces = [t for t in cu["traces"] if len(t["pts"]) > 1]
for v in vias: v["_mov"] = not v.get("_fp") and vk(v) not in FIXV and not fixed_net(v["net"])
for t in traces: t["_mov"] = tk(t) not in FIXT and not fixed_net(t["net"])
# PAIR_PUSH=1: a pair trace may get a jog only together with its partner, both by the same trapezoid (equal length)
PAIR_PUSH = bool(os.environ.get("PAIR_PUSH"))
for t in traces: t["_pair"] = PAIR_PUSH and tk(t) not in FIXT and t["net"] in PAIR_NETS and not t["net"].startswith("DDR_")
padg = lambda p: Point(p["x"], p["y"]).buffer(p["w"] / 2, 16) if p["shape"] == "circle" else box(p["x"] - p["w"] / 2, p["y"] - p["h"] / 2, p["x"] + p["w"] / 2, p["y"] + p["h"] / 2)
PADG = [padg(p) for p in pads]
line = lambda t: LineString([(p["x"], p["y"]) for p in t["pts"]])

def objs_near(x, y, r):
    """(kind, index) of copper within r of (x, y): traces, vias, pads (indexes rebuilt each round)"""
    q = Point(x, y).buffer(r)
    return [("t", int(i)) for i in TT.query(q)] + [("v", int(i)) for i in VT.query(q)] + [("p", int(i)) for i in PT.query(q)]

def clear(kind, i, kind2, j):
    """(copper gap, hole gaps) between two objects of different nets: copper gap on shared layers (None if no
    shared layer), and the list of hole-to-copper gaps (a via's hole to the other's copper)"""
    if kind == "t":
        a = traces[i]; ga = TG[i]; la = {a["layer"]}
    elif kind == "v":
        a = vias[i]; la = set(LAYERS)
    else:
        a = pads[i]; la = {a["layer"]}
    if kind2 == "t":
        b = traces[j]; lb = {b["layer"]}
    elif kind2 == "v":
        b = vias[j]; lb = set(LAYERS)
    else:
        b = pads[j]; lb = {b["layer"]}
    if not (la & lb): return None, []
    def gd(k, o, idx):  # (geometry for distance, half width added)
        if k == "t": return TG[idx], o["w"] / 2
        if k == "v": return Point(o["x"], o["y"]), o["d"] / 2
        return PADG[idx], 0
    A, ha = gd(kind, a, i); B, hb = gd(kind2, b, j)
    dist = A.distance(B)
    cg = dist - ha - hb; holes = []
    if kind == "v": holes.append(dist - a["hole"] / 2 - hb)
    if kind2 == "v": holes.append(dist - b["hole"] / 2 - ha)
    if kind == "v" and kind2 == "v": holes = [dist - (a["hole"] / 2 + b["d"] / 2), dist - (b["hole"] / 2 + a["d"] / 2)]
    return cg, holes

def net_of(k, i): return (traces if k == "t" else vias if k == "v" else pads)[i]["net"]
def local_state(items):
    """worst copper gap and the hole deficit sum / min hole gap over pairs involving the given items"""
    seen = set(); worst_cu = 9.0; deficit = 0.0; worst_h = 9.0
    for k, i in items:
        o = (traces if k == "t" else vias)[i]
        if k == "t":
            b = TG[i].bounds; cx, cy, r = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2, math.hypot(b[2] - b[0], b[3] - b[1]) / 2 + 0.6
        else:
            cx, cy, r = o["x"], o["y"], 0.6
        for k2, j in objs_near(cx, cy, r):
            if (k2, j) == (k, i) or net_of(k2, j) == o["net"]: continue
            key = tuple(sorted([(k, i), (k2, j)]))
            if key in seen: continue
            seen.add(key)
            cg, hs = clear(k, i, k2, j)
            if cg is None: continue
            worst_cu = min(worst_cu, cg)
            for h in hs:
                worst_h = min(worst_h, h)
                if h < HOLE: deficit += HOLE - h
    return worst_cu, deficit, worst_h

def rebuild():
    global TG, TT, VT, PT
    TG = [line(t) for t in traces]
    TT = STRtree([g.buffer(t["w"] / 2 + 0.15) for g, t in zip(TG, traces)])
    VT = STRtree([Point(v["x"], v["y"]).buffer(v["d"] / 2 + 0.15) for v in vias])
    PT = STRtree([g.buffer(0.15) for g in PADG])

def violations():
    out = []
    for i, v in enumerate(vias):
        for k2, j in objs_near(v["x"], v["y"], HOLE + 0.3):
            if (k2, j) == ("v", i) or net_of(k2, j) == v["net"]: continue
            cg, hs = clear("v", i, k2, j)
            if cg is None: continue
            h = min(hs) if k2 == "v" else hs[0]
            if h < HOLE - 1e-4: out.append((HOLE - h, i, k2, j))
    return sorted(out, reverse=True)

def attached(i):
    """traces of the via's net with an end on the via centre: (trace index, point index)"""
    v = vias[i]; out = []
    for k, j in objs_near(v["x"], v["y"], 0.05):
        if k == "t" and traces[j]["net"] == v["net"]:
            for pi in (0, len(traces[j]["pts"]) - 1):
                p = traces[j]["pts"][pi]
                if abs(p["x"] - v["x"]) < 1e-3 and abs(p["y"] - v["y"]) < 1e-3: out.append((j, pi))
    return out

def try_move(changes, items):
    """changes: list of (obj, field updates) applied, kept if better; returns True if kept"""
    before = local_state(items)
    saved = [(o, {k: o[k] for k in upd}) for o, upd in changes]
    for o, upd in changes: o.update(upd)
    for k, i in items:
        if k == "t": TG[i] = line(traces[i])
    after = local_state(items)
    ok = after[0] >= min(GAP, before[0]) - 1e-6 and after[2] >= before[2] - 1e-6 and after[1] < before[1] - 1e-5
    if not ok:
        for o, old in saved: o.update(old)
        for k, i in items:
            if k == "t": TG[i] = line(traces[i])
    return ok

def push_trace(ti, vx, vy, need):
    """jog trace ti away from (vx, vy) by need at its closest point"""
    t = traces[ti]; g = TG[ti]
    s = g.project(Point(vx, vy)); p = g.interpolate(s)
    dx, dy = p.x - vx, p.y - vy; n = math.hypot(dx, dy)
    if n < 1e-6: return False
    ux, uy = dx / n, dy / n
    pts = [dict(q) for q in t["pts"]]
    # existing interior vertex close to the closest point: push it; otherwise insert a vertex there
    acc, best = 0.0, None
    for k in range(1, len(pts) - 1):
        acc_k = g.project(Point(pts[k]["x"], pts[k]["y"]))
        if abs(acc_k - s) < 0.06: best = k
    if best is None:
        acc = 0.0
        for k in range(len(pts) - 1):
            seg = math.hypot(pts[k + 1]["x"] - pts[k]["x"], pts[k + 1]["y"] - pts[k]["y"])
            if acc + seg >= s - 1e-9:
                if s - acc < 0.02 or acc + seg - s < 0.02: return False  # at an end: move the via instead
                pts.insert(k + 1, {"x": p.x, "y": p.y}); best = k + 1; break
            acc += seg
    if best is None or best in (0, len(pts) - 1): return False
    for f in (1.0, 0.6, 1.5):
        d = min(STEP_MAX, need * f)
        np_ = [dict(q) for q in pts]; np_[best] = {"x": round(pts[best]["x"] + ux * d, 4), "y": round(pts[best]["y"] + uy * d, 4)}
        if try_move([(t, {"pts": np_})], [("t", ti)]): return True
    return False

def push_via(vi, ox, oy, need):
    v = vias[vi]; dx, dy = v["x"] - ox, v["y"] - oy; n = math.hypot(dx, dy)
    if n < 1e-6: return False
    ux, uy = dx / n, dy / n; att = attached(vi)
    for f in (1.0, 0.6, 1.5):
        d = min(STEP_MAX, need * f); nx, ny = round(v["x"] + ux * d, 4), round(v["y"] + uy * d, 4)
        ch = [(v, {"x": nx, "y": ny})]
        for tj, pi in att:
            pts = [dict(q) for q in traces[tj]["pts"]]; pts[pi] = {"x": nx, "y": ny}; ch.append((traces[tj], {"pts": pts}))
        if try_move(ch, [("v", vi)] + [("t", tj) for tj, _ in att]): return True
    return False

def seg_at(pts, s):
    """(segment index, position) of arc length s along pts"""
    acc = 0.0
    for k in range(len(pts) - 1):
        L = math.hypot(pts[k + 1]["x"] - pts[k]["x"], pts[k + 1]["y"] - pts[k]["y"])
        if acc + L >= s - 1e-9: return k, s - acc, L
        acc += L
    return None

def trapezoid(pts, s, half, ramp, ox, oy):
    """copy of pts with a jog centred at arc length s: flat 2*half long, ramps of length ramp, offset (ox, oy);
    None unless the whole jog lies inside one straight segment"""
    a = seg_at(pts, s - half - ramp); b = seg_at(pts, s + half + ramp)
    if not a or not b or a[0] != b[0] or a[1] < 0.02 or b[2] - b[1] < 0.02: return None
    k = a[0]; P0, P1 = pts[k], pts[k + 1]; L = a[2]
    ux, uy = (P1["x"] - P0["x"]) / L, (P1["y"] - P0["y"]) / L
    at = lambda d, off: {"x": round(P0["x"] + ux * d + (ox if off else 0), 4), "y": round(P0["y"] + uy * d + (oy if off else 0), 4)}
    d0 = a[1]
    new = [at(d0, 0), at(d0 + ramp, 1), at(d0 + ramp + 2 * half, 1), at(d0 + 2 * ramp + 2 * half, 0)]
    return pts[:k + 1] + new + pts[k + 1:]

def plen(pts): return sum(math.hypot(b["x"] - a["x"], b["y"] - a["y"]) for a, b in zip(pts, pts[1:]))

def push_pair(ti, vx, vy, need):
    """jog pair trace ti and its partner's parallel trace by the same trapezoid, away from (vx, vy)"""
    t = traces[ti]; g = TG[ti]; mate = PARTNER.get(t["net"])
    if not mate: return False
    s = g.project(Point(vx, vy)); p = g.interpolate(s)
    hit = seg_at(t["pts"], s)
    if not hit: return False
    k = hit[0]; P0, P1 = t["pts"][k], t["pts"][k + 1]; L = hit[2]
    if L < 1e-6: return False
    ux, uy = (P1["x"] - P0["x"]) / L, (P1["y"] - P0["y"]) / L; nx, ny = -uy, ux
    if (p.x - vx) * nx + (p.y - vy) * ny < 0: nx, ny = -nx, -ny
    # partner: same layer, parallel, 0.15 - 0.6 mm away at this point
    best = None
    for kk, j in objs_near(p.x, p.y, 0.7):
        if kk != "t" or traces[j]["net"] != mate or traces[j]["layer"] != t["layer"] or not traces[j]["_pair"]: continue
        sj = TG[j].project(p); q = TG[j].interpolate(sj); dq = q.distance(p)
        h = seg_at(traces[j]["pts"], sj)
        if not h or not (0.12 < dq < 0.6) or h[2] < 1e-6: continue
        Q0, Q1 = traces[j]["pts"][h[0]], traces[j]["pts"][h[0] + 1]
        vx2, vy2 = (Q1["x"] - Q0["x"]) / h[2], (Q1["y"] - Q0["y"]) / h[2]
        if abs(vx2 * uy - vy2 * ux) > 0.02: continue  # not parallel
        if best is None or dq < best[0]: best = (dq, j, sj)
    if not best: return False
    _, j, sj = best; m = traces[j]
    for half in (0.3, 0.2, 0.4):
        for ramp in (0.15, 0.25, 0.1):
            for f in (1.0, 1.5):
                d = min(STEP_MAX, need * f)
                a = trapezoid(t["pts"], s, half, ramp, nx * d, ny * d); b = trapezoid(m["pts"], sj, half, ramp, nx * d, ny * d)
                if not a or not b: continue
                # equal added length on both members (skew unchanged), to 1 um
                if abs((plen(a) - plen(t["pts"])) - (plen(b) - plen(m["pts"]))) > 1e-3: continue
                if try_move([(t, {"pts": a}), (m, {"pts": b})], [("t", ti), ("t", j)]): return True
    return False

rebuild()
v0 = violations(); print(f"start: {len({i for _, i, _, _ in v0})} vias below {HOLE} mm, {len(v0)} pairs, min {HOLE - v0[0][0]:.3f}" if v0 else "start: clean")
for rnd in range(ROUNDS):
    vs = violations()
    if not vs: break
    moved = 0
    for need, i, k2, j in vs:
        need += EPS; v = vias[i]
        if k2 == "t" and traces[j]["_mov"] and push_trace(j, v["x"], v["y"], need): moved += 1; continue
        if k2 == "t" and traces[j]["_pair"] and push_pair(j, v["x"], v["y"], need): moved += 1; continue
        o = (traces[j] if k2 == "t" else vias[j] if k2 == "v" else pads[j])
        if v["_mov"]:
            if k2 == "t": c = TG[j].interpolate(TG[j].project(Point(v["x"], v["y"]))); ox, oy = c.x, c.y
            elif k2 == "p": c = PADG[j].exterior.interpolate(PADG[j].exterior.project(Point(v["x"], v["y"]))); ox, oy = (o["x"], o["y"]) if PADG[j].contains(Point(v["x"], v["y"])) else (c.x, c.y)
            else: ox, oy = o["x"], o["y"]
            if push_via(i, ox, oy, need): moved += 1; continue
        if k2 == "v" and vias[j]["_mov"] and push_via(j, v["x"], v["y"], need): moved += 1; continue
    rebuild(); left = violations()
    print(f"round {rnd + 1}: {moved} moves, {len({i for _, i, _, _ in left})} vias below {HOLE} mm, {len(left)} pairs" + (f", min {HOLE - left[0][0]:.3f}" if left else ""))
    if not moved: break
cu["traces"] = [{k: v for k, v in t.items() if not k.startswith("_")} for t in traces] + [t for t in cu["traces"] if len(t["pts"]) <= 1]
cu["vias"] = [{k: x for k, x in v.items() if not k.startswith("_")} for v in vias if not v.get("_fp")]
json.dump(cu, open(CP, "w"))
left = violations(); fixed_left = [x for x in left if not vias[x[1]]["_mov"] and not (x[2] == "t" and traces[x[3]]["_mov"]) and not (x[2] == "v" and vias[x[3]]["_mov"])]
print(f"done: {len({i for _, i, _, _ in left})} vias below {HOLE} mm ({len(fixed_left)} pairs between fixed copper only)")
