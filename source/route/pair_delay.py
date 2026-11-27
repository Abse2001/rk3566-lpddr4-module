# P/N skew of the module's differential pairs measured on the final copper (not routes.json): each net's trace
# length per layer converted to delay with the stackup's ps/mm (outer microstrip / inner stripline, as in
# ddr_timing.py) plus its vias (the barrel between the layers the net uses at each via, stripline velocity x1.2). Also checks that the LPDDR4
# block on the board is the verified solver output (fixed.json DDR copper present unchanged in COPPER).
# Usage: COPPER=final/copper.json python3 pair_delay.py
import json, math, os, re, collections
D = os.path.dirname(os.path.abspath(__file__))
cu = json.load(open(os.environ.get("COPPER", D + "/final/copper.json")))
tm = json.load(open(D + "/ddr_timing.json"))["ps_per_mm"]
PS = {"outer": tm["outer_0.11"], "inner": tm["inner3_0.11"]}
VIA_PS = 1.548 * PS["inner"] * 1.2
VCAL = json.load(open(D + "/via_cal.json")) if os.path.exists(D + "/via_cal.json") else None  # ngspice via delay (via_cal.py)
L = collections.defaultdict(float); T = collections.defaultdict(float); V = collections.Counter()
for t in cu["traces"]:
    s = sum(math.hypot(b["x"] - a["x"], b["y"] - a["y"]) for a, b in zip(t["pts"], t["pts"][1:]))
    L[t["net"]] += s; T[t["net"]] += s * PS["outer" if t["layer"] in ("top", "bottom") else "inner"]
# a via's delay is its barrel between the layers the net actually uses there (traces ending on it, or a top /
# bottom pad it sits in), as in ddr_timing.py: |dz| x stripline ps/mm x 1.2
Z = {"top": 0, "inner1": 0.111, "inner2": 0.727, "inner3": 0.841, "inner4": 1.457, "bottom": 1.548}
P_ = json.load(open(D + "/../design/pads.json"))["pads"]
ends = collections.defaultdict(set)
for t in cu["traces"]:
    for q in (t["pts"][0], t["pts"][-1]): ends[(t["net"], round(q["x"], 3), round(q["y"], 3))].add(t["layer"])
VD = collections.defaultdict(float)
for v in cu["vias"]:
    V[v["net"]] += 1
    ls = set(ends.get((v["net"], round(v["x"], 3), round(v["y"], 3)), set()))
    for p in P_:
        if p["net"] == v["net"] and abs(p["x"] - v["x"]) < p["w"] / 2 and abs(p["y"] - v["y"]) < p["h"] / 2: ls.add(p["layer"])
    if len(ls) >= 2:
        span = max(Z[l] for l in ls) - min(Z[l] for l in ls)
        VD[v["net"]] += VCAL["ps_per_mm"] * span + VCAL["ps_fixed"] if VCAL else span * PS["inner"] * 1.2
names = set(L)
LIMIT_MM = {"HDMI": 0.13, "MIPI": 0.13, "PCIE": 0.13, "USB": 0.25}
ok = True; rows = []
for n in sorted(names):
    m = re.match(r"(.*?)(P|_P|DP)(_C)?$", n)
    if not m: continue
    q = m.group(1) + {"P": "N", "_P": "_N", "DP": "DM"}[m.group(2)] + (m.group(3) or "")
    if q not in names: continue
    dp, dq = T[n] + VD[n], T[q] + VD[q]
    lim = next((v for k, v in LIMIT_MM.items() if n.startswith(k)), 0.13) * PS["outer"]
    sk = abs(dp - dq); ok &= sk <= lim
    rows.append(f"{'PASS' if sk <= lim else 'FAIL'}  {n:22s} {L[n]:6.2f}/{L[q]:6.2f} mm  vias {V[n]}/{V[q]}  skew {sk:5.2f} ps (limit {lim:4.2f} ps)")
print("\n".join(rows))
fx = json.load(open(D + "/fixed.json"))
key = lambda t: (t["net"], t["layer"], tuple((round(p["x"], 4), round(p["y"], 4)) for p in t["pts"]))
have = {key(t) for t in cu["traces"]}
ddr = [t for t in fx["traces"] if t["net"].startswith("DDR_")]; ddr_nets = {t["net"] for t in ddr}
miss = [t["net"] for t in ddr if key(t) not in have]
extra = [t["net"] for t in cu["traces"] if t["net"] in ddr_nets and key(t) not in {key(x) for x in ddr}]
print(f"LPDDR4 block: {len(ddr)} solver traces, {len(miss)} missing/changed on the board, {len(extra)} extra DDR traces")
print("RESULT:", "PASS" if ok and not miss and not extra else "FAIL")
