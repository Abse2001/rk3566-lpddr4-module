# Exports the data behind research/signal-checks.html: ngspice eye diagrams (LPDDR4X DQ / CK at 2112 and 3120
# MT/s, HDMI pairs with equal and unequal vias), pair skew before / after, via calibration, via-hole spacing,
# LPDDR4 timing margins. Writes si/out/viz.json.
import os, sys, json, math, re, collections, importlib
R = os.path.dirname(os.path.abspath(__file__)) + "/../route"; S_ = R + "/.."
sys.path.insert(0, R); os.chdir(R)
os.environ["VDDQ"] = "0.6"; sys.argv = ["x", "ddr.lane.routed.json"]
import ddr_sim as DS
out = {}
def fold(t, v, delay, ui, nbits, start=12, pts=100):
    """eye traces: 2-UI windows starting half a UI before each bit, resampled to pts points"""
    traces = []
    for b in range(start, nbits - 3):
        t0 = delay + (b - 0.5) * ui; t1 = t0 + 2 * ui
        seg = [(ti - t0, vi) for ti, vi in zip(t, v) if t0 <= ti <= t1]
        if len(seg) < 4: continue
        rs = []
        for k in range(pts):
            x = 2 * ui * k / (pts - 1)
            j = min(range(len(seg)), key=lambda i: abs(seg[i][0] - x)); rs.append(round(seg[j][1], 4))
        traces.append(rs)
    return traces[:70]
for rate in (2112, 3120):
    DS.RATE = rate; DS.UI = 1e6 / rate
    d = DS.T["delay_ps"]["DQ8_a"]; t, v, pat = DS.run(["DQ8_a"], bits=90)
    h, w, _ = DS.eye(t, v[0], pat, d)
    out[f"dq_{rate}"] = {"ui": DS.UI, "traces": fold(t, v[0], d, DS.UI, 90), "height_mV": round(h * 1000), "width_ps": round(w)}
    d = DS.T["delay_ps"]["CK_t_a"]; t, v, pat = DS.run(["CK_t_a", "CK_c_a"], invert=("CK_c_a",), bits=90)
    dif = [a - b for a, b in zip(v[0], v[1])]; h, w, _ = DS.eye(t, dif, pat, d)
    out[f"ck_{rate}"] = {"ui": DS.UI, "traces": fold(t, dif, d, DS.UI, 90), "height_mV": round(h * 1000), "width_ps": round(w)}
# pairs on the final copper
os.environ["COPPER"] = R + "/final/copper.json"; sys.argv = ["x"]
src = open(R + "/pair_sim.py").read().split("RATE = {")[0]
g = {"__name__": "ps", "__file__": R + "/pair_sim.py"}; exec(src, g); S = g["S"]
def pair_wave(p, n, rate, cu_path=None):
    if cu_path:
        g2 = {"__name__": "ps", "__file__": R + "/pair_sim.py"}; os.environ["COPPER"] = cu_path; exec(src, g2); lane = g2["lane"]
        S.channel = g2["channel"]
    else: lane = g["lane"]; S.channel = g["channel"]
    S.R = {"traces": lane(p) + lane(n)}; S.UI = 1e6 / rate
    t, v, pat = S.run([p, n], invert=(n,), bits=60)
    delay = sum(td for _, td, _ in S.pieces(p))
    # one rising edge of P (and falling N) around bit 20, zoomed +-0.6 UI
    k = next(b for b in range(20, 55) if pat[b] and not pat[b - 1])
    tc = delay + k * S.UI; win = [(round(ti - tc, 2), round(a, 4), round(b, 4)) for ti, a, b in zip(t, v[0], v[1]) if abs(ti - tc) <= 0.6 * S.UI]
    dif = [a - b for a, b in zip(v[0], v[1])]
    return {"edge": win[::2], "eye": fold(t, dif, delay, S.UI, 60), "ui": S.UI}
out["hdmi_d0"] = pair_wave("HDMI_TX_D0P", "HDMI_TX_D0N", 3400)
out["hdmi_clk"] = pair_wave("HDMI_TX_CLKP", "HDMI_TX_CLKN", 3400)
out["hdmi_clk_old"] = pair_wave("HDMI_TX_CLKP", "HDMI_TX_CLKN", 3400, S_ + "/costdown/tune/copper.json")
# pair skew tables (ngspice crossing skew) from the result files
def table(path):
    rows = []
    for l in open(path):
        m = re.match(r"(\S+)\s+(\d+) Mb/s\s+vias (\d+)/(\d+)\s+P/N crossing skew\s+([\d.]+) ps", l)
        if m: rows.append({"pair": m.group(1)[:-1] if m.group(1).endswith("P") else m.group(1), "rate": int(m.group(2)), "vias": [int(m.group(3)), int(m.group(4))], "skew": float(m.group(5))})
    return rows
out["skew_now"] = table(S_ + "/../research/ngspice-pairs-final.txt")
if os.path.exists(S_ + "/../research/ngspice-pairs-v0113.txt"): out["skew_before"] = table(S_ + "/../research/ngspice-pairs-v0113.txt")
out["via_cal"] = json.load(open(R + "/via_cal.json"))
# via hole to other copper: minimum per via, before the push solver and now
def holes(cp, pp):
    os.environ["COPPER"] = cp; os.environ["PLANES"] = pp
    import io, contextlib
    gg = {"__file__": S_ + "/check.py", "__name__": "__main__"}
    with contextlib.redirect_stdout(io.StringIO()):
        try: exec(open(S_ + "/check.py").read(), gg)
        except SystemExit: pass
    per = collections.defaultdict(lambda: 1.0)
    for l, d, n, k, on, x, y in gg["holecu_v"]: per[(x, y, n)] = min(per[(x, y, n)], d)
    bins = collections.Counter(round(math.floor(v * 200) / 200, 3) for v in per.values())
    return {"bins": sorted(bins.items()), "total_vias": None, "below_018": sum(1 for v in per.values() if v < 0.18), "min": min(per.values())}
os.chdir(S_)
out["holes_before"] = holes(S_ + "/costdown/final/copper.json", S_ + "/costdown/final/planes.json")
out["holes_now"] = holes(S_ + "/route/final/copper.json", S_ + "/route/final/planes.json")
# LPDDR4 timing: each Rockchip rule's measured value against its limit
lines = os.popen(f"cd {R} && python3 ddr_timing.py ddr.lane.routed.json").read().splitlines()
tim = []
for l in lines:
    m = re.match(r"(PASS|FAIL)\s+(.*?)(-?[\d.]+) ps \(limit ([\d.]+) ps", l)
    if m: tim.append({"rule": m.group(2).strip().rstrip(":"), "value": abs(float(m.group(3))), "limit": float(m.group(4))})
out["ddr_timing"] = tim
json.dump(out, open(os.path.dirname(os.path.abspath(__file__)) + "/out/viz.json", "w"))
print("wrote", {k: (len(v) if isinstance(v, (list, dict)) else v) for k, v in out.items()})
