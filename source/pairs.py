# Length and P/N skew of the module's differential pairs (HDMI, MIPI DSI/CSI, PCIe, USB) from routed copper.
# usage: pairs.py [routes.json]
import json, sys, os, math, re
D = os.path.dirname(os.path.abspath(__file__))
rt = json.load(open(sys.argv[1] if len(sys.argv) > 1 else D + "/route/routes.json"))["nets"]
# Lengths in outer-layer-equivalent mm (= delay / outer ps per mm): inner-layer copper weighted by its slower
# stripline velocity, each via by its barrel between the layers the net uses there (ddr_timing.py stackup model).
# Matching P and N in these units matches them in time. OLD_VIA=1 gives the old count (0.6 mm per via).
_tm = json.load(open(D + "/route/ddr_timing.json"))["ps_per_mm"]
K = lambda l: 1.0 if l in ("top", "bottom") else _tm["inner3_0.11"] / _tm["outer_0.11"]
ZL = {"top": 0, "inner1": 0.111, "inner2": 0.727, "inner3": 0.841, "inner4": 1.457, "bottom": 1.548}
_pads = json.load(open(D + "/design/pads.json"))["pads"]
def via_len(n, r, v):
    ls = {s["layer"] for s in r["segs"] for q in (s["pts"][0], s["pts"][-1]) if abs(q["x"] - v["x"]) < 1e-3 and abs(q["y"] - v["y"]) < 1e-3}
    ls |= {p["layer"] for p in _pads if p["net"] == n and abs(p["x"] - v["x"]) < p["w"] / 2 and abs(p["y"] - v["y"]) < p["h"] / 2}
    return (max(ZL[l] for l in ls) - min(ZL[l] for l in ls)) * _tm["inner3_0.11"] * 1.2 / _tm["outer_0.11"] if len(ls) >= 2 else 0.0
def length(n):
    r = rt.get(n)
    if not r: return None
    if os.environ.get("OLD_VIA"):
        return sum(math.hypot(b["x"] - a["x"], b["y"] - a["y"]) for s in r["segs"] for a, b in zip(s["pts"], s["pts"][1:])) + 0.6 * len(r["vias"])
    return sum(K(s["layer"]) * math.hypot(b["x"] - a["x"], b["y"] - a["y"]) for s in r["segs"] for a, b in zip(s["pts"], s["pts"][1:])) + sum(via_len(n, r, v) for v in r["vias"])
pairs = []
names = sorted(rt)
for n in names:
    m = re.match(r"(.*?)(P|_P|DP)(_C)?$", n)
    if not m: continue
    base, suf, c = m.group(1), m.group(2), m.group(3) or ""
    neg = base + {"P": "N", "_P": "_N", "DP": "DM"}[suf] + c
    if neg in rt: pairs.append((n, neg))
LIMIT = {"HDMI": 0.13, "MIPI": 0.13, "PCIE": 0.13, "USB": 0.25}  # mm (about 5 mil; USB 2.0 is lenient)
worst = 0
for p, q in pairs:
    lp, lq = length(p), length(q)
    if lp is None or lq is None: continue
    sk = abs(lp - lq); lim = next((v for k, v in LIMIT.items() if p.startswith(k)), 0.13)
    worst = max(worst, sk / lim)
    print(f"{p:22} {lp:6.2f} mm  {q:22} {lq:6.2f} mm  skew {sk:5.2f} mm {'OK' if sk <= lim else 'TOO LONG'}")
print(f"{len(pairs)} pairs; worst skew / limit = {worst:.1f}")
