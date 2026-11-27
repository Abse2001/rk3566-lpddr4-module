# Calibrates the extra delay of a through via (barrel between two layers + its pad capacitance) with ngspice, in the
# same model pair_sim.py / ddr_sim.py use: a 52 ohm line of 60 ps, then either nothing or a via (45 ohm line over the
# barrel span at the stripline velocity, 0.3 pF pad), then 60 ps more, generic 40 ohm driver / 60 ohm + 0.8 pF load,
# 80 ps edges. The via's delay = difference of the 50 % crossing times. Fits delay = a * span_mm + b and writes
# via_cal.json {"ps_per_mm": a, "ps_fixed": b, "spans": {...}} for pairs.py / tune_pairs.py / pair_delay.py.
import json, os, subprocess, tempfile
D = os.path.dirname(os.path.abspath(__file__))
tm = json.load(open(D + "/ddr_timing.json"))["ps_per_mm"]; PSI = tm["inner3_0.11"]
Z = {"top": 0, "inner1": 0.111, "inner2": 0.727, "inner3": 0.841, "inner4": 1.457, "bottom": 1.548}
def cross_time(via_span):
    net = ["* via cal", "V0 s 0 PWL(0p 0 100p 0 180p 1.1 3000p 1.1)", "Rs s d 40", "T1 d 0 a 0 Z0=52 TD=60p"]
    if via_span is None: net += ["Rv a b 0.001"]
    else: net += [f"Tv a 0 b 0 Z0=45 TD={via_span * PSI:.3f}p", "Cv b 0 0.3p"]
    net += ["T2 b 0 r 0 Z0=52 TD=60p", "Rt r 0 60", "Ct r 0 0.8p", ".tran 0.5p 1500p", ".control", "run"]
    out = tempfile.mktemp(suffix=".txt"); net += [f"wrdata {out} v(r)", ".endc", ".end"]
    cir = tempfile.mktemp(suffix=".cir"); open(cir, "w").write("\n".join(net))
    subprocess.run(["ngspice", "-b", cir], capture_output=True, text=True, timeout=120)
    rows = [list(map(float, l.split())) for l in open(out) if l.strip()]
    vmax = max(r[1] for r in rows); th = vmax / 2
    for a, b in zip(rows, rows[1:]):
        if a[1] < th <= b[1]: return (a[0] + (th - a[1]) / (b[1] - a[1]) * (b[0] - a[0])) * 1e12
t0 = cross_time(None); spans = {}
for a, b in (("top", "inner3"), ("inner3", "bottom"), ("top", "bottom"), ("top", "inner2"), ("inner2", "bottom")):
    sp = abs(Z[a] - Z[b]); spans[f"{a}-{b}"] = (round(sp, 3), round(cross_time(sp) - t0, 3))
xs = [v[0] for v in spans.values()]; ys = [v[1] for v in spans.values()]
n = len(xs); mx, my = sum(xs) / n, sum(ys) / n
a = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs); b = my - a * mx
json.dump({"ps_per_mm": a, "ps_fixed": b, "spans": spans, "old_model_ps_per_mm": PSI * 1.2}, open(D + "/via_cal.json", "w"), indent=1)
for k, (sp, d) in spans.items(): print(f"{k:14s} span {sp:.3f} mm: via adds {d:6.2f} ps (fit {a * sp + b:6.2f}, old model {sp * PSI * 1.2:6.2f})")
print(f"fit: via delay = {a:.2f} ps/mm x span + {b:.2f} ps")
