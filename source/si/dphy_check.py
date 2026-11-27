# MIPI D-PHY compliance check of the module's MIPI pairs, from the final copper, against the D-PHY limits that
# intra-pair skew actually affects (values as in TI SN65DPHY440SS, which follows the D-PHY spec):
#   - HS receiver: differential signal must exceed 70 mV (|VID|) at the sampling point
#   - common-mode noise: transmitter dVCMTX(HF) <= 15 mVrms above 450 MHz (MIPI; strictest budget our board's skew
#     adds to), receiver tolerates dVCMRX(HF) 100 mV, dVCMRX(LF) +-50 mV
#   - data-to-clock: +-0.15 UI above 1 Gb/s (the whole link's budget; the module's share is reported)
# Model: per line 50 ohm source around VCM 200 mV, 200 mV differential into the 100 ohm load (400 mV open circuit), 0.3 UI 20-80 % edges; the channel from the copper
# (pair_sim.py: per-layer lines, vias as lumped L-C with 0.3 pF pad); receiver 2 x 50 ohm to a centre tap with
# 10 pF to ground, 1 pF pad per line. PRBS7 at 1.5 Gb/s (RK3566 D-PHY maximum). Usage: COPPER=... python3 dphy_check.py
import os, sys, json, math, re, subprocess, tempfile
import numpy as np
R = os.path.dirname(os.path.abspath(__file__)) + "/../route"; sys.path.insert(0, R); os.chdir(R); sys.argv = ["x"]
g = {"__name__": "ps", "__file__": R + "/pair_sim.py"}; exec(open(R + "/pair_sim.py").read().split("RATE = {")[0], g)
S, lane, channel = g["S"], g["lane"], g["channel"]
RATE = 1500e6; UI = 1e12 / RATE; VCM, VOD = 0.2, 0.4;  # VOD here is the open-circuit swing: D-PHY's 200 mV is specified into the 100 ohm load (50 ohm source per line halves it)
TR = 0.3 * UI / 0.6  # 0-100 % edge for 0.3 UI 20-80 %
def pwl(bits, sign):
    pts, t = [], 0.0; v0 = VCM + sign * (VOD / 2 if bits[0] else -VOD / 2); pts.append(f"0p {v0:.4f}")
    for b in bits:
        v = VCM + sign * (VOD / 2 if b else -VOD / 2)
        if v != v0: pts += [f"{t:.1f}p {v0:.4f}", f"{t + TR:.1f}p {v:.4f}"]; v0 = v
        t += UI
    return " ".join(pts)
def run(p, n, nbits=127):
    S.R = {"traces": lane(p) + lane(n)}; S.channel = channel
    pat = S.prbs7(nbits); net = ["* D-PHY lane"]
    for i, (nm, sg) in enumerate(((p, 1), (n, -1))):
        net += [f"V{i} s{i} 0 PWL({pwl(pat, sg)})", f"Rs{i} s{i} d{i} 50"] + channel(f"c{i}_", nm, f"d{i}", f"r{i}")
        net += [f"Rt{i} r{i} ct 50", f"Cp{i} r{i} 0 1p"]
    net += ["Cct ct 0 10p", ".options reltol=1e-4", f".tran 2p {nbits * UI + 2000:.0f}p", ".control", "run"]
    out = tempfile.mktemp(suffix=".txt"); net += [f"wrdata {out} v(r0) v(r1)", ".endc", ".end"]
    cir = tempfile.mktemp(suffix=".cir"); open(cir, "w").write("\n".join(net))
    subprocess.run(["ngspice", "-b", cir], capture_output=True, text=True, timeout=900)
    a = np.loadtxt(out); return a[:, 0] * 1e12, a[:, 1], a[:, 3], pat
def analyse(t, vp, vn, pat, delay):
    vd = vp - vn; vc = (vp + vn) / 2
    m = t > delay + 10 * UI; tt, vd2, vc2 = t[m], vd[m], vc[m]
    # differential eye at the bit centre: smallest |VID| over all bits, and the eye width where |VID| >= 70 mV
    ph = ((tt - delay) / UI) % 1.0; bit = ((tt - delay) / UI).astype(int)
    ok = bit < len(pat) - 1; ph, bit, vdv = ph[ok], bit[ok], vd2[ok]
    sgn = np.where(np.array(pat)[bit] == 1, 1, -1)
    cen = np.abs(ph - 0.5) < 0.05; vid_min = float(np.min(sgn[cen] * vdv[cen]))
    bins = np.linspace(0, 1, 101); good = []
    for k in range(100):
        s = (ph >= bins[k]) & (ph < bins[k + 1])
        if s.any(): good.append(float(np.min(sgn[s] * vdv[s])) >= 0.07)
    width = sum(good) / 100 * UI
    # common mode: HF (> 450 MHz) RMS and peak, LF (50-450 MHz) peak, via FFT on a uniform grid
    tu = np.arange(tt[0], tt[-1], 2.0); cu = np.interp(tu, tt, vc2); cu -= cu.mean()
    f = np.fft.rfftfreq(len(cu), 2e-12); F = np.fft.rfft(cu)
    hf = np.fft.irfft(np.where(f > 450e6, F, 0), len(cu)); lf = np.fft.irfft(np.where((f > 50e6) & (f <= 450e6), F, 0), len(cu))
    return {"vid_min_mV": round(vid_min * 1000, 1), "eye_width_ps": round(width), "eye_width_UI": round(width / UI, 3),
            "cm_hf_rms_mV": round(float(np.sqrt(np.mean(hf ** 2))) * 1000, 2), "cm_hf_peak_mV": round(float(np.max(np.abs(hf))) * 1000, 1),
            "cm_lf_peak_mV": round(float(np.max(np.abs(lf))) * 1000, 1)}
pd = {}
for l in os.popen("COPPER=" + os.environ.get("COPPER", R + "/final/copper.json") + " python3 " + R + "/pair_delay.py").read().splitlines():
    pass
# lane delays (ps) from the calibrated delay model, P/N average, for data-to-clock skew
cu = json.load(open(os.environ.get("COPPER", R + "/final/copper.json")))
import collections
tm = json.load(open(R + "/ddr_timing.json"))["ps_per_mm"]; vcal = json.load(open(R + "/via_cal.json"))
Z = {"top": 0, "inner1": 0.111, "inner2": 0.727, "inner3": 0.841, "inner4": 1.457, "bottom": 1.548}
pads = json.load(open(R + "/../design/pads.json"))["pads"]; dl = collections.defaultdict(float); ends = collections.defaultdict(set)
for t_ in cu["traces"]:
    dl[t_["net"]] += sum(math.hypot(b["x"] - a["x"], b["y"] - a["y"]) for a, b in zip(t_["pts"], t_["pts"][1:])) * (tm["outer_0.11"] if t_["layer"] in ("top", "bottom") else tm["inner3_0.11"])
    for q in (t_["pts"][0], t_["pts"][-1]): ends[(t_["net"], round(q["x"], 3), round(q["y"], 3))].add(t_["layer"])
for v in {(v["net"], round(v["x"], 3), round(v["y"], 3)): v for v in cu["vias"]}.values():
    ls = set(ends.get((v["net"], round(v["x"], 3), round(v["y"], 3)), set())) | {p["layer"] for p in pads if p["net"] == v["net"] and abs(p["x"] - v["x"]) < p["w"] / 2 and abs(p["y"] - v["y"]) < p["h"] / 2}
    if len(ls) >= 2: dl[v["net"]] += vcal["ps_per_mm"] * (max(Z[l] for l in ls) - min(Z[l] for l in ls)) + vcal["ps_fixed"]
groups = {"CSI": ("MIPI_CSI_RX_CLK1", [f"MIPI_CSI_RX_D{i}" for i in range(4)]), "DSI": ("MIPI_DSI_TX1_CLK", [f"MIPI_DSI_TX1_D{i}" for i in range(4)])}
names = {t_["net"] for t_ in cu["traces"]}
res = {"limits": {"vid_min_mV": 70, "cm_hf_rms_mV_tx": 15, "cm_hf_peak_mV_rx": 100, "cm_lf_peak_mV_rx": 50, "data_to_clock_UI": 0.15}, "pairs": {}, "lanes": {}}
for gname, (clk, data) in groups.items():
    lanes = [clk] + [d for d in data if d + "P" in names]
    for ln in lanes:
        p, n = ln + "P", ln + "N"
        t, vp, vn, pat = run(p, n)
        delay = sum(td for _, td, _ in S.pieces(p))
        r = analyse(t, vp, vn, pat, delay); r["vias"] = [len({(round(v["x"], 3), round(v["y"], 3)) for v in cu["vias"] if v["net"] == x}) for x in (p, n)]
        res["pairs"][ln] = r; print(gname, ln, r, flush=True)
    ck = (dl[clk + "P"] + dl[clk + "N"]) / 2
    for ln in lanes[1:]:
        d = (dl[ln + "P"] + dl[ln + "N"]) / 2 - ck
        res["lanes"][ln] = {"to_clock_ps": round(d, 1), "to_clock_UI": round(d / UI, 3)}
        print(gname, ln, "data-to-clock", res["lanes"][ln], flush=True)
json.dump(res, open(os.path.dirname(os.path.abspath(__file__)) + "/out/dphy.json", "w"), indent=1)
bad = [k for k, r in res["pairs"].items() if r["vid_min_mV"] < 70 or r["cm_hf_rms_mV"] > 15 or r["cm_hf_peak_mV"] > 100 or r["cm_lf_peak_mV"] > 50]
badl = [k for k, r in res["lanes"].items() if abs(r["to_clock_UI"]) > 0.15]
print("RESULT:", "PASS" if not bad and not badl else f"FAIL {bad} {badl}")
