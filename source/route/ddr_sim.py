# ngspice simulation of routed LPDDR4 nets with generic I/O models (no vendor IBIS):
#   driver: ideal LVSTL-like source, VDDQ 1.1 V, 40 ohm output, 80 ps 20-80 % edges
#   receiver: 60 ohm ODT to VSSQ (LPDDR4 terminates to ground) + 0.8 pF pad
#   channel: each routed piece in path order as a lossless line (TLINE): per-layer Z0 and delay from ddr_timing.py,
#            the 0.09 mm neck-downs as their own impedance, each via as a 0.6 pF-loaded line over its barrel length
# Outputs per net: eye height / width at the receiver for a PRBS7 pattern, and for a pair the P/N crossing skew.
# Usage: python3 ddr_sim.py [ddr.lane.routed.json] [MTps]
import json, math, os, subprocess, sys, tempfile
D = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(sys.argv[1] if len(sys.argv) > 1 else D + "/ddr.lane.routed.json"))
VDDQ = float(os.environ.get("VDDQ", 1.1))  # 0.6 for LPDDR4X
RATE = float(sys.argv[2]) if len(sys.argv) > 2 else 1560.0  # MT/s
T = json.load(open(D + "/ddr_timing.json"))
UI = 1e6 / RATE  # ps
Z = {"top": 0, "inner1": 0.111, "inner2": 0.727, "inner3": 0.841, "inner4": 1.457, "bottom": 1.548}
def lay(l): return "outer" if l in ("top", "bottom") else "inner3"
def pieces(name):
    """(Z0 ohm, delay ps, kind) along the net in route order"""
    out = []
    for t in R["traces"]:
        if t["connection_name"] != name: continue
        r = t["route"]
        for a, b in zip(r, r[1:]):
            if a["route_type"] == b["route_type"] == "wire" and a["layer"] == b["layer"]:
                s = math.hypot(b["x"] - a["x"], b["y"] - a["y"])
                if s < 1e-6: continue
                w = "0.09" if a.get("width", 0.11) < 0.1 else "0.11"
                k = f"{lay(a['layer'])}_{w}"
                out.append((T["z0"][k], s * T["ps_per_mm"][k], "wire"))
            if b["route_type"] == "via":
                out.append((45.0, abs(Z[b["from_layer"]] - Z[b["to_layer"]]) * T["ps_per_mm"]["inner3_0.11"], "via"))
    return out
def prbs7(n):
    s = 0x7F; bits = []
    for _ in range(n):
        b = ((s >> 6) ^ (s >> 5)) & 1; s = ((s << 1) | b) & 0x7F; bits.append(b)
    return bits
def pwl(bits, invert=False, tr=80):
    pts = [(0, 0)]; v0 = None; t = 0.0
    for b in bits:
        v = VDDQ if (b ^ invert) else 0.0
        if v0 is None: pts = [(0, v)]
        elif v != v0: pts += [(t, v0), (t + tr / 0.6, v)]
        v0 = v; t += UI
    pts.append((t, v0))
    return " ".join(f"{p[0]:.1f}p {p[1]:.3f}" for p in pts)
def merged(name):
    """consecutive pieces with the same impedance joined; pieces under 1 ps folded into their neighbour"""
    out = []
    for z0, td, kind in pieces(name):
        if out and (abs(out[-1][0] - z0) < 0.5 or td < 1.0) and kind == "wire" and out[-1][2] == "wire":
            pz, pt, pk = out[-1]; out[-1] = ((pz * pt + z0 * td) / (pt + td), pt + td, "wire")
        else: out.append((z0, td, kind))
    return out
def channel(prefix, name, src, rx):
    lines = []; node = src
    for k, (z0, td, kind) in enumerate(merged(name)):
        nxt = f"{prefix}{k}"
        lines.append(f"T{prefix}{k} {node} 0 {nxt} 0 Z0={z0:.1f} TD={td:.3f}p")
        if kind == "via": lines.append(f"C{prefix}v{k} {nxt} 0 0.3p")
        node = nxt
    lines.append(f"R{prefix}j {node} {rx} 0.01")
    return lines
def run(nets, invert=(), bits=127):
    pat = prbs7(bits)
    net = ["* LPDDR4 channel, generic I/O"]
    for i, n in enumerate(nets):
        net += [f"V{i} s{i} 0 PWL({pwl(pat, n in invert)})", f"Rs{i} s{i} d{i} 40"]
        net += channel(f"n{i}_", n, f"d{i}", f"r{i}")
        net += [f"Rt{i} r{i} 0 60", f"Ct{i} r{i} 0 0.8p"]
    tstop = bits * UI + 2000
    out = tempfile.mktemp(suffix=".txt")
    net += [".options reltol=1e-4", f".tran 5p {tstop:.0f}p", ".control", "run",
            "wrdata " + out + " " + " ".join(f"v(r{i})" for i in range(len(nets))), ".endc", ".end"]
    cir = tempfile.mktemp(suffix=".cir"); open(cir, "w").write("\n".join(net))
    subprocess.run(["ngspice", "-b", cir], capture_output=True, text=True)
    rows = [list(map(float, l.split())) for l in open(out) if l.strip()]
    t = [r[0] * 1e12 for r in rows]; v = [[r[2 * i + 1] for r in rows] for i in range(len(nets))]
    return t, v, pat
def eye(t, v, pat, delay):
    """eye height at the centre and eye width at Vref, from the bits after the first 10"""
    hi = [x for x in v if x > 0]; vref = (max(v) + min(v)) / 2
    folded = {}
    for ti, vi in zip(t, v):
        k = (ti - delay) / UI
        if k < 10 or k >= len(pat) - 1: continue
        b = int(k); ph = (k - b)
        folded.setdefault(round(ph * 50), []).append((vi, pat[b]))
    hgt = []
    for ph, xs in folded.items():
        ones = [x for x, b in xs if b]; zeros = [x for x, b in xs if not b]
        if ones and zeros: hgt.append((ph, min(ones) - max(zeros)))
    open_ = [ph for ph, h in hgt if h > 0.05]
    best = max(hgt, key=lambda p: p[1]) if hgt else (0, 0)
    return best[1], len(open_) / 50 * UI, vref
if __name__ == "__main__":
    print(f"data rate {RATE:.0f} MT/s, UI {UI:.0f} ps; generic 40 ohm driver, 60 ohm ODT, 0.8 pF")
    worst = sorted(((T["delay_ps"][n], n) for n in T["delay_ps"] if n.startswith("DQ") and "DQS" not in n), reverse=True)[:2]
    for d, n in worst + [(T["delay_ps"]["CA0_a"], "CA0_a")]:
        t, v, pat = run([n])
        h, w, vref = eye(t, v[0], pat, d)
        print(f"{n:8s} delay {d:6.1f} ps  vias {sum(1 for p in pieces(n) if p[2] == 'via')}  eye height {h * 1000:5.0f} mV  eye width {w:4.0f} ps of {UI:.0f}")
    for p, nn in (("CK_t_a", "CK_c_a"), ("CK_t_b", "CK_c_b"), ("DQS1_t_a", "DQS1_c_a"), ("DQS0_t_b", "DQS0_c_b")):
        t, v, pat = run([p, nn], invert=(nn,))
        dif = [a - b for a, b in zip(v[0], v[1])]
        # P/N crossing skew: compare each member's own threshold crossing times
        def cross(x):
            th = (max(x) + min(x)) / 2; c = []
            for k in range(1, len(x)):
                if (x[k - 1] - th) * (x[k] - th) < 0: c.append(t[k - 1] + (th - x[k - 1]) / (x[k] - x[k - 1]) * (t[k] - t[k - 1]))
            return c
        cp, cn = cross(v[0]), cross(v[1])
        sk = [min(abs(a - b) for b in cn) for a in cp[10:60]] if cn else [0]
        h, w, _ = eye(t, dif, pat, T["delay_ps"][p])
        print(f"{p}/{nn} pair: P/N crossing skew {sum(sk) / len(sk):5.1f} ps; differential eye height {h * 1000:5.0f} mV, width {w:4.0f} ps")
