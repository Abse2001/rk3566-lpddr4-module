# ngspice check of the module's differential pairs on the final copper: each member becomes a chain of lossless
# lines (Z0 and delay per layer from ddr_timing.json, vias as 45 ohm stubs + 0.3 pF, same model as ddr_sim.py),
# driven with PRBS7 and its complement at the interface's top rate. Reports the P/N crossing skew at the receiver
# and the differential eye. Generic driver/termination (ddr_sim.py: 40 ohm source, 60 ohm + 0.8 pF per leg), so
# the eye is indicative; the skew is the point of the check.
# Usage: COPPER=final/copper.json python3 pair_sim.py
import json, os, re, sys, collections
D = os.path.dirname(os.path.abspath(__file__))
sys.argv = [sys.argv[0]]  # ddr_sim reads argv for its own inputs
import ddr_sim as S
cu = json.load(open(os.environ.get("COPPER", D + "/final/copper.json")))
pads = json.load(open(D + "/../design/pads.json"))["pads"]
Z = S.Z
ends = collections.defaultdict(set)
for t in cu["traces"]:
    for q in (t["pts"][0], t["pts"][-1]): ends[(t["net"], round(q["x"], 3), round(q["y"], 3))].add(t["layer"])
def lane(net):
    out = []
    for t in cu["traces"]:
        if t["net"] == net and len(t["pts"]) > 1:
            out.append({"connection_name": net, "route": [{"route_type": "wire", "x": p["x"], "y": p["y"], "layer": t["layer"], "width": max(t["w"], 0.1)} for p in t["pts"]]})
    for v in cu["vias"]:
        if v["net"] != net: continue
        ls = set(ends.get((net, round(v["x"], 3), round(v["y"], 3)), set()))
        ls |= {p["layer"] for p in pads if p["net"] == net and abs(p["x"] - v["x"]) < p["w"] / 2 and abs(p["y"] - v["y"]) < p["h"] / 2}
        if len(ls) < 2: continue
        a, b = min(ls, key=lambda l: Z[l]), max(ls, key=lambda l: Z[l])
        out.append({"connection_name": net, "route": [{"route_type": "wire", "x": v["x"], "y": v["y"], "layer": a}, {"route_type": "via", "x": v["x"], "y": v["y"], "from_layer": a, "to_layer": b}]})
    return out
# copper has no route order: the net's wire delay is split into (vias + 1) equal pieces and one via (45 ohm barrel
# line + 0.3 pF pad, as ddr_sim.py / via_cal.py) goes between consecutive pieces, so vias sit apart as on the board
# instead of back to back (back-to-back vias make ngspice crawl and distort the result).
def channel(prefix, name, src, rx):
    pcs = S.merged(name); wires = [(z, td) for z, td, kind in pcs if kind == "wire"]; vias = [td for z, td, kind in pcs if kind == "via"]
    tot = sum(td for _, td in wires); zavg = sum(z * td for z, td in wires) / tot if tot else 50.0
    lines, node = [], src; n = len(vias) + 1
    for k in range(n):
        nxt = f"{prefix}w{k}"; lines.append(f"T{prefix}w{k} {node} 0 {nxt} 0 Z0={zavg:.1f} TD={tot / n:.3f}p"); node = nxt
        if k < len(vias):
            # a via is electrically short: lumped L-C with the barrel line's L = Z0*TD and C = TD/Z0 (plus the 0.3 pF
            # pad), same delay and load as the 45 ohm line, without the tiny time steps a 5 ps line forces on ngspice
            nxt = f"{prefix}v{k}"; td = vias[k] * 1e-12
            lines.append(f"L{prefix}v{k} {node} {nxt} {45.0 * td * 1e9:.4f}n"); lines.append(f"C{prefix}v{k} {nxt} 0 {(td / 45.0) * 1e12 + 0.3:.4f}p"); node = nxt
    lines.append(f"R{prefix}j {node} {rx} 0.01")
    return lines
S.channel = channel
RATE = {"HDMI": 3400, "MIPI": 1500, "PCIE": 5000, "USB": 480}
names = {t["net"] for t in cu["traces"]}
pairs = []
for n in sorted(names):
    m = re.match(r"(.*?)(P|_P|DP)(_C)?$", n)
    if m:
        q = m.group(1) + {"P": "N", "_P": "_N", "DP": "DM"}[m.group(2)] + (m.group(3) or "")
        if q in names: pairs.append((n, q))
worst = 0
for p, nn in pairs:
    S.R = {"traces": lane(p) + lane(nn)}
    rate = next((v for k, v in RATE.items() if p.startswith(k)), 1000); S.UI = 1e6 / rate
    t, v, pat = S.run([p, nn], invert=(nn,))
    def cross(x):
        th = (max(x) + min(x)) / 2; c = []
        for k in range(1, len(x)):
            if (x[k - 1] - th) * (x[k] - th) < 0: c.append(t[k - 1] + (th - x[k - 1]) / (x[k] - x[k - 1]) * (t[k] - t[k - 1]))
        return c
    cp, cn = cross(v[0]), cross(v[1])
    sk = [min(abs(a - b) for b in cn) for a in cp[10:60]] if cn else []
    if not sk: print(f"{p:20s} no crossings found"); continue
    delay = sum(td for _, td, _ in S.pieces(p))
    h, w, _ = S.eye(t, [a - b for a, b in zip(v[0], v[1])], pat, delay)
    skew = sum(sk) / len(sk); worst = max(worst, skew)
    print(f"{p:20s} {rate:5d} Mb/s  vias {sum(1 for x in S.pieces(p) if x[2] == 'via')}/{sum(1 for x in S.pieces(nn) if x[2] == 'via')}  P/N crossing skew {skew:5.2f} ps  diff eye {h * 1000:5.0f} mV x {w:4.0f} ps of {S.UI:.0f} ps")
print(f"{len(pairs)} pairs; worst P/N crossing skew {worst:.2f} ps")
