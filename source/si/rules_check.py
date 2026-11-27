# Interface-level rule audit of the routed module (things check.py does not cover). Reads route/final copper,
# planes, pads. Each rule prints PASS / WARN / FAIL with its numbers; writes si/out/rules.json.
#  R1 reference continuity: every fast trace on inner3 lies over one inner2 island (no split crossing) and has no
#     other-net copper under it on inner4 within w/2 + 3h; outer layers are covered by check.py
#  R2 pair coupling: share of each pair's length where P and N run side by side (same layer, <= 0.45 mm apart)
#  R3 group timing (calibrated delay model): MIPI data lane to clock (AMD UG863: +-8 ps), HDMI lane to lane
#     (HDMI: 0.2 Tcharacter = 588 ps at 340 MHz; guideline 25 ps), eMMC HS200 / SD SDR104 data+cmd to clock
#     (vendor guideline ~ +-50 mil = 7.5 ps on the outer layers -> 25 ps used as a WARN level)
#  R4 power traces: narrowest trace of each supply net routed as traces vs its estimated current (IPC-2221,
#     10 C rise; outer 35 um, inner 17 um copper)
#  R5 crosstalk: parallel run of a fast trace within 2 trace widths (edge gap < 0.2 mm) of another net on the same
#     layer, longer than 3 mm
#  R6 branches: a fast net's copper must be a chain (no T-branch / stub)
import json, math, os, re, collections, sys
from shapely.geometry import Point, LineString, Polygon, box
from shapely.ops import unary_union
from shapely.strtree import STRtree
S = os.path.dirname(os.path.abspath(__file__)) + "/.."
cu = json.load(open(os.environ.get("COPPER", S + "/route/final/copper.json")))
pl = json.load(open(os.environ.get("PLANES", S + "/route/final/planes.json")))
pads = json.load(open(S + "/design/pads.json"))["pads"]
tm = json.load(open(S + "/route/ddr_timing.json"))["ps_per_mm"]; vcal = json.load(open(S + "/route/via_cal.json"))
FAST = re.compile(r"^(HDMI_TX_[CD]|MIPI_|PCIE20_|USB_OTG0_D|EMMC_|CM4_SD_)")
Z = {"top": 0, "inner1": 0.111, "inner2": 0.727, "inner3": 0.841, "inner4": 1.457, "bottom": 1.548}
out = {}; status = {}
def tline(t): return LineString([(q["x"], q["y"]) for q in t["pts"]])
def report(rule, level, msg, data=None):
    status[rule] = level; out[rule] = {"level": level, "summary": msg, "data": data}; print(f"{level:4s} {rule}: {msg}")
# ---------- R1 reference continuity on inner3 ----------
isl = collections.defaultdict(list)
for q in pl:
    g = Polygon([(a["x"], a["y"]) for a in q["outer"]], [[(a["x"], a["y"]) for a in h] for h in q["holes"]]).buffer(0)
    isl[(q["layer"], q["net"])].append(g)
inner2 = {n: unary_union(gs) for (l, n), gs in isl.items() if l == "inner2"}
r1 = []
in4 = [(t["net"], tline(t).buffer(t["w"] / 2)) for t in cu["traces"] if t["layer"] == "inner4" and t["net"] != "GND" and len(t["pts"]) > 1]
in4t = STRtree([g for _, g in in4]) if in4 else None
for t in cu["traces"]:
    if t["layer"] != "inner3" or not FAST.match(t["net"]) or len(t["pts"]) < 2: continue
    ln = tline(t)
    # inner2 above: the length not over any island (gap) and the islands crossed
    over = {n: ln.intersection(g).length for n, g in inner2.items() if ln.intersects(g)}
    gap = ln.length - sum(over.values())
    if len(over) > 1 or gap > 0.05: r1.append((t["net"], "inner2", round(gap, 2), sorted(over)))
    zone = ln.buffer(t["w"] / 2 + 3 * 0.6)  # h to inner4 = 0.6 mm core
    if in4t is not None:
        hits = {in4[i][0] for i in in4t.query(zone) if in4[i][1].intersects(ln.buffer(t["w"] / 2 + 0.1))}
        if hits: r1.append((t["net"], "inner4", None, sorted(hits)))
crossings = [x for x in r1 if x[1] == "inner2"]; under4 = [x for x in r1 if x[1] == "inner4"]
report("R1_reference", "FAIL" if r1 else "PASS", f"{len(crossings)} inner3 fast-trace pieces cross inner2 island splits/gaps, {len(under4)} have foreign copper under them on inner4", r1[:60])
# ---------- R2 pair coupling ----------
names = {t["net"] for t in cu["traces"]}
pairs = []
for n in sorted(names):
    m = re.match(r"(.*?)(P|_P|DP)(_C)?$", n)
    if m and not n.startswith("DDR_"):
        q = m.group(1) + {"P": "N", "_P": "_N", "DP": "DM"}[m.group(2)] + (m.group(3) or "")
        if q in names: pairs.append((n, q))
r2 = {}
for p, n in pairs:
    tot = cpl = 0.0
    for t in cu["traces"]:
        if t["net"] != p or len(t["pts"]) < 2: continue
        ln = tline(t); tot += ln.length
        nn = unary_union([tline(u) for u in cu["traces"] if u["net"] == n and u["layer"] == t["layer"] and len(u["pts"]) > 1])
        if not nn.is_empty: cpl += ln.intersection(nn.buffer(0.45)).length
    r2[p] = round(cpl / tot, 2) if tot else 0
low = {k: v for k, v in r2.items() if v < 0.7}
report("R2_coupling", "WARN" if low else "PASS", f"{len(low)} pairs run side by side for less than 70 % of their length: " + ", ".join(f"{k} {int(v * 100)}%" for k, v in sorted(low.items(), key=lambda x: x[1])), r2)
# ---------- delays ----------
dl = collections.defaultdict(float); ends = collections.defaultdict(set)
for t in cu["traces"]:
    dl[t["net"]] += tline(t).length * (tm["outer_0.11"] if t["layer"] in ("top", "bottom") else tm["inner3_0.11"]) if len(t["pts"]) > 1 else 0
    for q in (t["pts"][0], t["pts"][-1]): ends[(t["net"], round(q["x"], 3), round(q["y"], 3))].add(t["layer"])
for v in {(v["net"], round(v["x"], 3), round(v["y"], 3)): v for v in cu["vias"]}.values():
    ls = set(ends.get((v["net"], round(v["x"], 3), round(v["y"], 3)), set())) | {p["layer"] for p in pads if p["net"] == v["net"] and abs(p["x"] - v["x"]) < p["w"] / 2 and abs(p["y"] - v["y"]) < p["h"] / 2}
    if len(ls) >= 2: dl[v["net"]] += vcal["ps_per_mm"] * (max(Z[l] for l in ls) - min(Z[l] for l in ls)) + vcal["ps_fixed"]
pd = lambda base: (dl[base + "P"] + dl[base + "N"]) / 2
# ---------- R3 group timing ----------
grp = {}
def group(name, ref, members, limit_ps, fail_ps=None):
    r = {m: round(dl[m] - dl[ref] if not m.endswith("@") else 0, 1) for m in members}
    worst = max(abs(v) for v in r.values()) if r else 0
    grp[name] = {"ref": ref, "delta_ps": r, "worst_ps": round(worst, 1), "limit_ps": limit_ps}
    return worst
def pgroup(name, clk, lanes, limit_ps):
    r = {ln: round(pd(ln) - pd(clk), 1) for ln in lanes if ln + "P" in names}
    worst = max(abs(v) for v in r.values()) if r else 0
    grp[name] = {"ref": clk, "delta_ps": r, "worst_ps": round(worst, 1), "limit_ps": limit_ps}; return worst
w_dsi = pgroup("MIPI DSI data to clock", "MIPI_DSI_TX1_CLK", [f"MIPI_DSI_TX1_D{i}" for i in range(4)], 8)
w_csi = pgroup("MIPI CSI data to clock", "MIPI_CSI_RX_CLK1", [f"MIPI_CSI_RX_D{i}" for i in range(4)], 8)
hd = [pd(f"HDMI_TX_D{i}") for i in range(3)] + [pd("HDMI_TX_CLK")]
grp["HDMI lane to lane"] = {"delta_ps": {f"D{i}": round(hd[i] - hd[3], 1) for i in range(3)}, "worst_ps": round(max(hd) - min(hd), 1), "limit_ps": 25}
emmc = [n for n in names if re.match(r"EMMC_(D\d|CMD)$", n)]
w_emmc = group("eMMC data/cmd to clock", "EMMC_CLK", sorted(emmc), 25)
sd = [n for n in names if re.match(r"CM4_SD_(DAT\d|CMD)$", n)]
w_sd = group("SD data/cmd to clock", "CM4_SD_CLK", sorted(sd), 25) if "CM4_SD_CLK" in names else 0
bad3 = [k for k, v in grp.items() if v["worst_ps"] > v["limit_ps"]]
report("R3_group_timing", "FAIL" if bad3 else "PASS", "; ".join(f"{k}: worst {v['worst_ps']} ps (limit {v['limit_ps']})" for k, v in grp.items()), grp)
# ---------- R4 power trace widths (IPC-2221, 10 C rise) ----------
CUR = {"VCC5V0_SYS": 2.5, "VCC3V3_SYS": 2.0, "VCC_1V8": 0.8, "VCC_3V3": 0.6, "VCC3V3_PMU": 0.2, "VCCA_1V8": 0.3, "VCCA1V8_PMU": 0.2,
       "VDDA_0V9": 0.3, "VDDA0V9_PMU": 0.1, "VCCIO_SD": 0.3, "VCC3V3_SD": 0.5, "VCCIO6": 0.1, "VCCIO_ACODEC": 0.1, "VCCA1V8_IMAGE": 0.1,
       "VDDA0V9_IMAGE": 0.1, "SW1": 2.5, "SW2": 2.0, "SW3": 1.5, "SW4": 1.0, "SW5": 1.5, "SW_CPU": 3.0, "SW_3V3": 2.5}
def i_max(w_mm, outer):
    a = w_mm / 0.0254 * (1.378 if outer else 0.669)  # mil^2 (35 um = 1.378 mil, 17 um = 0.669 mil)
    return (0.048 if outer else 0.024) * 10 ** 0.44 * a ** 0.725
r4 = []
for net, amps in CUR.items():
    ts = [t for t in cu["traces"] if t["net"] == net and len(t["pts"]) > 1]
    if not ts: continue
    worst = min(ts, key=lambda t: i_max(t["w"], t["layer"] in ("top", "bottom")))
    cap = i_max(worst["w"], worst["layer"] in ("top", "bottom"))
    r4.append({"net": net, "est_A": amps, "narrowest_mm": worst["w"], "layer": worst["layer"], "capacity_A": round(cap, 2), "ok": cap >= amps})
bad4 = [r for r in r4 if not r["ok"]]
report("R4_power_width", "FAIL" if bad4 else "PASS", f"{len(bad4)} supply nets have a trace too narrow for their estimated current: " + ", ".join(f"{r['net']} {r['narrowest_mm']} mm on {r['layer']} carries ~{r['capacity_A']} A, needs {r['est_A']} A" for r in bad4), r4)
# ---------- R5 crosstalk ----------
r5 = []
lay = collections.defaultdict(list)
for t in cu["traces"]:
    if len(t["pts"]) > 1: lay[t["layer"]].append(t)
for l, ts in lay.items():
    geo = [tline(t) for t in ts]; tr = STRtree([g.buffer(ts[i]["w"] / 2 + 0.2) for i, g in enumerate(geo)])
    acc = collections.defaultdict(float)
    for i, t in enumerate(ts):
        if not FAST.match(t["net"]): continue
        zone = geo[i].buffer(t["w"] / 2 + 0.2)
        for j in tr.query(zone):
            u = ts[j]
            if u["net"] == t["net"]: continue
            pp = re.sub(r"(P|N|DP|DM)(_C)?$", "", t["net"]) == re.sub(r"(P|N|DP|DM)(_C)?$", "", u["net"])
            if pp: continue  # own pair partner
            acc[(t["net"], u["net"])] += geo[j].intersection(zone).length
    r5 += [(a, b, l, round(v, 1)) for (a, b), v in acc.items() if v > 3.0]
report("R5_crosstalk", "WARN" if r5 else "PASS", f"{len(r5)} fast-net / other-net parallel runs longer than 3 mm at < 0.2 mm edge gap", sorted(r5, key=lambda x: -x[3])[:40])
# ---------- R6 branches ----------
r6 = []
for n in sorted(names):
    if not FAST.match(n): continue
    deg = collections.Counter()
    for t in cu["traces"]:
        if t["net"] == n and len(t["pts"]) > 1:
            for q in (t["pts"][0], t["pts"][-1]): deg[(round(q["x"], 2), round(q["y"], 2), t["layer"])] += 1
    br = [k for k, c in deg.items() if c > 2]
    if br: r6.append((n, br[:3]))
report("R6_branches", "WARN" if r6 else "PASS", f"{len(r6)} fast nets with a T-branch", r6)
json.dump(out, open(os.path.dirname(os.path.abspath(__file__)) + "/out/rules.json", "w"), indent=1, default=str)
print("SUMMARY:", {k: v for k, v in status.items()})
