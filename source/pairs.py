# Length and P/N skew of the module's differential pairs (HDMI, MIPI DSI/CSI, PCIe, USB) from routed copper.
# usage: pairs.py [routes.json]
import json, sys, os, math, re
D = os.path.dirname(os.path.abspath(__file__))
rt = json.load(open(sys.argv[1] if len(sys.argv) > 1 else D + "/route/routes.json"))["nets"]
def length(n):
    r = rt.get(n)
    if not r: return None
    L = sum(math.hypot(b["x"] - a["x"], b["y"] - a["y"]) for s in r["segs"] for a, b in zip(s["pts"], s["pts"][1:]))
    return L + 0.6 * len(r["vias"])  # ~0.6 mm per through via in a 1.6 mm board
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
