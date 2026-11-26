# LPDDR4 timing as propagation delay instead of length. A signal is faster on the outer layers (microstrip, field
# partly in air) than on inner3 (stripline, field fully in FR-4), so two equal lengths on different layers arrive
# at different times. Per-layer delay comes from the JLC06161H-1080A stackup:
#   outer (top/bottom): 0.11 mm trace on 0.0764 mm 1080 prepreg (Er 3.91), 1 oz, under solder mask
#     -> Hammerstad-Jensen effective Er, +4 % for the mask
#   inner3: between inner2 (0.0994 mm 3313, Er 4.1) and inner4 (0.6 mm core, Er 4.6) -> stripline; the field sits
#     mostly in the thin prepreg towards inner2, effective Er weighted by the plane coupling
#   via: the barrel between the two layers it joins at the stripline velocity, x1.2 for the pad capacitance
# Groups and limits: Rockchip RK356x LPDDR4 rules (RK3568 HDG table 33), converted from mil to ps at the faster
# (outer) velocity so the time limit is the stricter one.
# Usage: python3 ddr_timing.py [ddr.lane.routed.json] [ddr.input.json]
import json, math, sys, os
D = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(sys.argv[1] if len(sys.argv) > 1 else D + "/ddr.lane.routed.json"))
I = json.load(open(sys.argv[2] if len(sys.argv) > 2 else D + "/ddr.input.json"))
C0 = 299.792458  # mm/ns
VIA_K = 1.2  # via barrel at the stripline velocity, +20 % for its pads (same as the solver's viaDelayFactor)
def microstrip(w, h, t, er):
    # Hammerstad-Jensen with thickness correction
    weff = w + t / math.pi * math.log(4 * math.e / math.sqrt((t / h) ** 2 + (t / (w * math.pi + 1.1 * t * math.pi)) ** 2)) * (1 + 1 / er) / 2
    u = weff / h
    a = 1 + math.log((u ** 4 + (u / 52) ** 2) / (u ** 4 + 0.432)) / 49 + math.log(1 + (u / 18.1) ** 3) / 18.7
    b = 0.564 * ((er - 0.9) / (er + 3)) ** 0.053
    ee = (er + 1) / 2 + (er - 1) / 2 * (1 + 10 / u) ** (-a * b)
    f = 6 + (2 * math.pi - 6) * math.exp(-((30.666 / u) ** 0.7528))
    z0 = 60 / math.sqrt(ee) * math.log(f / u + math.sqrt(1 + (2 / u) ** 2))
    return ee * 1.04, z0 / math.sqrt(1.04)  # solder mask: a little more Er, a little less Z
def stripline(w, h1, er1, h2, er2, t):
    # asymmetric stripline (IPC-2141 form); effective Er weighted by each plane's share of the capacitance (~1/h)
    c1, c2 = 1 / h1, 1 / h2
    ee = (er1 * c1 + er2 * c2) / (c1 + c2)
    H = h1 + h2 + t
    z0 = 80 / math.sqrt(ee) * math.log(1.9 * (2 * h1 + t) / (0.8 * w + t)) * (1 - h1 / (4 * (h1 + h2 + t)))
    return ee, z0
EE = {}
for w in (0.09, 0.11):
    eo, zo = microstrip(w, 0.0764, 0.035, 3.91)
    ei, zi = stripline(w, 0.0994, 4.1, 0.6, 4.6, 0.0152)
    EE[("outer", w)] = (eo, zo); EE[("inner3", w)] = (ei, zi)
ps_mm = lambda ee: 1000 * math.sqrt(ee) / C0
Z = {"top": 0, "inner1": 0.111, "inner2": 0.727, "inner3": 0.841, "inner4": 1.457, "bottom": 1.548}
def lay(l): return "outer" if l in ("top", "bottom") else "inner3"
delay, length = {}, {}
for t in R["traces"]:
    n = t["connection_name"]
    if n.startswith("power_"): continue
    r = t["route"]; d = L = 0.0
    for a, b in zip(r, r[1:]):
        if a["route_type"] == b["route_type"] == "wire" and a["layer"] == b["layer"]:
            s = math.hypot(b["x"] - a["x"], b["y"] - a["y"]); w = 0.09 if a.get("width", 0.11) < 0.1 else 0.11
            d += s * ps_mm(EE[(lay(a["layer"]), w)][0]); L += s
    for p in r:
        if p["route_type"] == "via":
            d += abs(Z[p["from_layer"]] - Z[p["to_layer"]]) * ps_mm(EE[("inner3", 0.11)][0]) * VIA_K
    delay[n] = delay.get(n, 0) + d; length[n] = length.get(n, 0) + L
MIL = 0.0254
fast = ps_mm(EE[("outer", 0.11)][0])
lim = lambda mil: mil * MIL * fast
print("stackup: outer 0.11 mm: Er_eff %.2f, %.2f ps/mm, Z0 %.0f ohm | inner3 0.11 mm: Er_eff %.2f, %.2f ps/mm, Z0 %.0f ohm | 0.09 mm neck: outer %.0f / inner %.0f ohm" % (
    EE[("outer", .11)][0], ps_mm(EE[("outer", .11)][0]), EE[("outer", .11)][1], EE[("inner3", .11)][0], ps_mm(EE[("inner3", .11)][0]), EE[("inner3", .11)][1], EE[("outer", .09)][1], EE[("inner3", .09)][1]))
ok = True
def line(p, m):
    global ok
    ok &= p; print(("PASS  " if p else "FAIL  ") + m)
for ch in "ab":
    ck = (delay[f"CK_t_{ch}"] + delay[f"CK_c_{ch}"]) / 2
    line(abs(delay[f"CK_t_{ch}"] - delay[f"CK_c_{ch}"]) <= lim(12), f"CK_{ch} P/N skew {abs(delay[f'CK_t_{ch}'] - delay[f'CK_c_{ch}']):.1f} ps (limit {lim(12):.1f} ps = 12 mil)")
    ca = [f"CA{i}_{ch}" for i in range(6)] + [f"CS0_{ch}", f"CKE0_{ch}", f"ODT_{ch}"]
    w = max(ca, key=lambda n: abs(delay[n] - ck))
    line(abs(delay[w] - ck) <= lim(500), f"CA_{ch} to CK worst {w}: {delay[w] - ck:+.1f} ps (limit {lim(500):.0f} ps = 500 mil)")
    for b in (0, 1):
        dqs = (delay[f"DQS{b}_t_{ch}"] + delay[f"DQS{b}_c_{ch}"]) / 2
        line(abs(delay[f"DQS{b}_t_{ch}"] - delay[f"DQS{b}_c_{ch}"]) <= lim(12), f"DQS{b}_{ch} P/N skew {abs(delay[f'DQS{b}_t_{ch}'] - delay[f'DQS{b}_c_{ch}']):.1f} ps (limit {lim(12):.1f} ps)")
        dq = [f"DQ{i}_{ch}" for i in range(8 * b, 8 * b + 8)] + [f"DMI{b}_{ch}"]
        w = max(dq, key=lambda n: abs(delay[n] - dqs))
        line(abs(delay[w] - dqs) <= lim(600), f"BYTE{b}_{ch} DQ/DMI to DQS worst {w}: {delay[w] - dqs:+.1f} ps (limit {lim(600):.0f} ps = 600 mil)")
        line(abs(dqs - ck) <= lim(1200), f"DQS{b}_{ch} to CK {dqs - ck:+.1f} ps (limit {lim(1200):.0f} ps = 1200 mil)")
print("RESULT:", "PASS" if ok else "FAIL")
json.dump({"delay_ps": delay, "length_mm": length, "ps_per_mm": {f"{k[0]}_{k[1]}": ps_mm(v[0]) for k, v in EE.items()}, "z0": {f"{k[0]}_{k[1]}": v[1] for k, v in EE.items()}}, open(D + "/ddr_timing.json", "w"), indent=1)
