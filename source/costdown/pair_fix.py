# Re-routes differential pairs whose P and N have different via counts, one pair at a time, with reroute.py
# PAIR_VIA=1 (second member changes layer only beside the first one's vias). Tries both orders, via costs, search
# margins and diagonal steps; keeps the shortest attempt where both members route with equal via counts.
# Usage: DIR=costdown/pf python3 costdown/pair_fix.py   (DIR holds routes.json + copper.json, rewritten)
import json, os, re, shutil, subprocess, collections, math
S = os.path.dirname(os.path.abspath(__file__)) + "/.."; F = os.path.abspath(os.environ["DIR"])
def vias(cu, n): return sum(1 for v in cu["vias"] if v["net"] == n)
def plen(cu, n): return sum(math.hypot(b["x"] - a["x"], b["y"] - a["y"]) for t in cu["traces"] if t["net"] == n for a, b in zip(t["pts"], t["pts"][1:]))
cu = json.load(open(F + "/copper.json")); names = {t["net"] for t in cu["traces"]}
pairs = []
for n in sorted(names):
    m = re.match(r"(.*?)(P|_P|DP)(_C)?$", n)
    if m and not n.startswith("DDR_"):
        q = m.group(1) + {"P": "N", "_P": "_N", "DP": "DM"}[m.group(2)] + (m.group(3) or "")
        if q in names and vias(cu, n) != vias(cu, q): pairs.append((n, q))
print("pairs to fix:", pairs)
for P, N in pairs:
    shutil.copy(F + "/routes.json", F + "/r.base"); shutil.copy(F + "/copper.json", F + "/c.base")
    best = None
    for order in ((P, N), (N, P)):
        for vc in ("0.6", "2", "4"):
            for mb in ("4", "6"):
                for diag in ("", "1"):
                    shutil.copy(F + "/r.base", F + "/r.try"); shutil.copy(F + "/c.base", F + "/c.try")
                    env = dict(os.environ, PAIR_VIA="1", M="0.004", VIA_COST=vc, MARGIN_BOX=mb, ROUTES=F + "/r.try", COPPER=F + "/c.try", NETS=",".join(order))
                    if diag: env["DIAG"] = "1"
                    else: env.pop("DIAG", None)
                    out = subprocess.run(["python3", S + "/route/reroute.py"], env=env, capture_output=True, text=True, cwd=S).stdout
                    if "FAILED" in out: continue
                    c = json.load(open(F + "/c.try"))
                    if vias(c, P) != vias(c, N): continue
                    L = plen(c, P) + plen(c, N)
                    if best is None or L < best[0]:
                        best = (L, order, vc, mb, diag, vias(c, P)); shutil.copy(F + "/r.try", F + "/r.best"); shutil.copy(F + "/c.try", F + "/c.best")
    if best:
        shutil.copy(F + "/r.best", F + "/routes.json"); shutil.copy(F + "/c.best", F + "/copper.json")
        print(f"{P}: fixed, {best[5]}/{best[5]} vias, {best[0]:.2f} mm total (order {best[1][0]} first, VIA_COST {best[2]}, box {best[3]}, DIAG {best[4] or 0})", flush=True)
    else:
        shutil.copy(F + "/r.base", F + "/routes.json"); shutil.copy(F + "/c.base", F + "/copper.json")
        print(f"{P}: NOT fixed (no attempt routed both members with equal vias)", flush=True)
