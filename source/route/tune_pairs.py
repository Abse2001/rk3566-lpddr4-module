# P/N length matching of the differential pairs: the shorter member gets square bumps on its longest straight
# runs, bulging away from its partner, until the two lengths agree within TOL. A bump is kept only if it clears all
# other copper on its layer by GAP (and pads, vias). Rewrites routes.json and copper.json.
import json, os, math, re
from shapely.geometry import LineString, Point, box
from shapely.strtree import STRtree
D = os.path.dirname(os.path.abspath(__file__))
RP, CP = os.environ.get("ROUTES", D + "/routes.json"), os.environ.get("COPPER", D + "/copper.json")
rt = json.load(open(RP)); cu = json.load(open(CP))
pads = json.load(open(D + "/../design/pads.json"))["pads"]
GAP, TOL, VIA_LEN = 0.1, 0.05, 0.6
nets = rt["nets"]
# DELAY=1: match P and N in time, not millimetres: each layer's length is weighted by its delay relative to the
# outer layers (inner stripline is slower), and a via counts its barrel between the layers the net uses there
# (same stackup model as ddr_timing.py / pair_delay.py). Lengths are in outer-layer-equivalent mm.
DELAY = bool(os.environ.get("DELAY"))
if DELAY:
    _tm = json.load(open(D + "/ddr_timing.json"))["ps_per_mm"]
    K = {l: (1.0 if l in ("top", "bottom") else _tm["inner3_0.11"] / _tm["outer_0.11"]) for l in ("top", "inner1", "inner2", "inner3", "inner4", "bottom")}
    ZL = {"top": 0, "inner1": 0.111, "inner2": 0.727, "inner3": 0.841, "inner4": 1.457, "bottom": 1.548}
    VK = _tm["inner3_0.11"] * 1.2 / _tm["outer_0.11"]
else:
    K = collections_K = None
def via_len(n, v):
    if not DELAY: return VIA_LEN
    ls = {s["layer"] for s in nets[n]["segs"] for q in (s["pts"][0], s["pts"][-1]) if abs(q["x"] - v["x"]) < 1e-3 and abs(q["y"] - v["y"]) < 1e-3}
    ls |= {p["layer"] for p in pads if p["net"] == n and abs(p["x"] - v["x"]) < p["w"] / 2 and abs(p["y"] - v["y"]) < p["h"] / 2}
    return (max(ZL[l] for l in ls) - min(ZL[l] for l in ls)) * VK if len(ls) >= 2 else 0.0
def length(n):
    r = nets[n]; k = (lambda l: K[l]) if DELAY else (lambda l: 1.0)
    return sum(k(s["layer"]) * math.hypot(b["x"] - a["x"], b["y"] - a["y"]) for s in r["segs"] for a, b in zip(s["pts"], s["pts"][1:])) + sum(via_len(n, v) for v in r["vias"])
pairs = []
for n in nets:
    m = re.match(r"(.*?)(P|_P|DP)(_C)?$", n)
    if not m: continue
    neg = m.group(1) + {"P": "N", "_P": "_N", "DP": "DM"}[m.group(2)] + (m.group(3) or "")
    if neg in nets: pairs.append((n, neg))
def obstacles(layer, skip_net):
    gs = []
    for t in cu["traces"]:
        if t["layer"] == layer and t["net"] != skip_net:
            for a, b in zip(t["pts"], t["pts"][1:]): gs.append(LineString([(a["x"], a["y"]), (b["x"], b["y"])]).buffer(t["w"] / 2))
    for v in cu["vias"]:
        # JLCPCB: via hole to other copper 0.2 mm, i.e. 0.15 mm from a 0.15/0.25 mm via's pad
        if v["net"] != skip_net: gs.append(Point(v["x"], v["y"]).buffer(v["d"] / 2 + (max(0, 0.2 - (v["d"] - v["hole"]) / 2 - GAP) if os.environ.get("HOLE_RULE") else 0)))
    # a fast trace keeps its reference ground layer clear: slow traces on inner1 (under top) / inner4 (above bottom)
    # count as obstacles, grown by 3x the 0.0764 mm prepreg minus the clearance the bump check adds
    gl = {"top": "inner1", "bottom": "inner4"}.get(layer)
    if gl:
        for t in cu["traces"]:
            if t["layer"] == gl and t["net"] != "GND":
                for a, b in zip(t["pts"], t["pts"][1:]): gs.append(LineString([(a["x"], a["y"]), (b["x"], b["y"])]).buffer(t["w"] / 2 + 3 * 0.0764 - GAP))
    for p in pads:
        if p["layer"] == layer and p["net"] != skip_net: gs.append(box(p["x"] - p["w"] / 2, p["y"] - p["h"] / 2, p["x"] + p["w"] / 2, p["y"] + p["h"] / 2))
    return gs
report = []
for P_, N_ in pairs:
    lp, ln = length(P_), length(N_)
    short, long_ = (P_, N_) if lp < ln else (N_, P_)
    need = abs(lp - ln)
    if need <= TOL: report.append((P_, round(need, 3), "ok")); continue
    partner_geom = [LineString([(a["x"], a["y"]), (b["x"], b["y"])]) for s in nets[long_]["segs"] for a, b in zip(s["pts"], s["pts"][1:])]
    done = 0.0
    segs = nets[short]["segs"]
    MIN_L = float(os.environ.get("MIN_L", 0.5)); AMPS = tuple(float(a) for a in os.environ.get("AMPS", "0.45,0.35,0.25,0.15").split(",")); PITCH, BW = 0.4, 0.2  # bump every 0.4 mm, 0.2 mm wide
    for rnd in range(40):  # one bumped piece per round: the straight pieces change as bumps go in
        before = done
        cands = sorted(((math.hypot(b["x"] - a["x"], b["y"] - a["y"]), si, k) for si, s in enumerate(segs) for k, (a, b) in enumerate(zip(s["pts"], s["pts"][1:]))), reverse=True)
        used = set()
        for L, si, k in cands:
            if done >= need - TOL or L < MIN_L: break
            if (si, k) in used: continue
            s = segs[si]; a, b = s["pts"][k], s["pts"][k + 1]; w = s["w"]
            obs = obstacles(s["layer"], short); tree = STRtree(obs)
            ux, uy = (b["x"] - a["x"]) / L, (b["y"] - a["y"]) / L
            nx, ny = -uy, ux
            mid = Point((a["x"] + b["x"]) / 2, (a["y"] + b["y"]) / 2)
            if partner_geom and min(g.distance(Point(mid.x + nx * 0.3, mid.y + ny * 0.3)) for g in partner_geom) < min(g.distance(Point(mid.x - nx * 0.3, mid.y - ny * 0.3)) for g in partner_geom):
                nx, ny = -nx, -ny  # first try bulging away from the partner
            nb = int((L - 0.3) / PITCH)
            if nb < 1: continue
            kl = K[s["layer"]] if DELAY else 1.0
            rem = (need - done) / kl  # physical length still to add on this layer
            best = None
            for side in (1, -1):
                for amp_max in AMPS:
                    nb_use = min(nb, max(1, math.ceil(rem / (2 * amp_max))))
                    amp = min(amp_max, rem / (2 * nb_use))
                    if amp < 0.02: continue
                    start = (L - nb_use * PITCH) / 2
                    pts = [a]
                    for q in range(nb_use):
                        t0 = start + q * PITCH + (PITCH - BW) / 2; t1 = t0 + BW
                        p0 = (a["x"] + ux * t0, a["y"] + uy * t0); p1 = (a["x"] + ux * t1, a["y"] + uy * t1)
                        sx, sy = nx * side * amp, ny * side * amp
                        pts += [{"x": p0[0], "y": p0[1]}, {"x": p0[0] + sx, "y": p0[1] + sy}, {"x": p1[0] + sx, "y": p1[1] + sy}, {"x": p1[0], "y": p1[1]}]
                    pts.append(b)
                    geom = LineString([(q["x"], q["y"]) for q in pts]).buffer(w / 2)
                    if any(obs[j].distance(geom) < GAP - 1e-6 for j in tree.query(geom.buffer(GAP))): continue
                    best = (pts, 2 * amp * nb_use * kl); break
                if best: break
            if not best: continue
            pts, gain = best
            s["pts"] = s["pts"][:k] + [{"x": round(q["x"], 4), "y": round(q["y"], 4)} for q in pts] + s["pts"][k + 2:]
            done += gain
            # keep the copper list in step for the next obstacle checks
            cu["traces"] = [t for t in cu["traces"] if t["net"] != short] + [dict(t, net=short) for t in segs]
            # indices after this segment shifted: recompute candidates next round
            break
        if done == before: break
        if done < need - TOL: continue
    report.append((P_, round(abs(length(P_) - length(N_)), 3), "tuned" if abs(length(P_) - length(N_)) <= TOL + 0.02 else "STILL SKEWED"))
json.dump(rt, open(RP, "w"))
json.dump(cu, open(CP, "w"))
for r in report: print(r)
