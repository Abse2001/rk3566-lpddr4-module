# Fixed copper in board coordinates, with module net names: the routed LPDDR4 block (ddr.lane.routed.json) and
# the power-ball fanout (power.fanout.json), both made with the RK3566 at the origin. A fanout whose ball is
# not a supply ball in the corrected ball map (rk3566-balls.json) is dropped: those balls are signals.
# Output: fixed.json {traces: [{pts, layer, w, net}], vias: [{x, y, d, hole, net}]}
import json, os
D = os.path.dirname(os.path.abspath(__file__))
net = json.load(open(D + "/../design/netlist.json"))
pins = {c["ref"]: c["pins"] for c in net["components"]}
RK = (15.2, -19.0)
traces, vias, dropped = [], [], []
def add(t, name):
    r = t["route"]
    cur, layer = [], r[0].get("layer")
    def flush():
        if len(cur) > 1:
            traces.append({"pts": [{"x": round(p["x"] + RK[0], 5), "y": round(p["y"] + RK[1], 5)} for p in cur], "layer": layer, "w": cur[0].get("width", 0.11), "net": name})
    for p in r:
        if p["route_type"] == "via":
            flush(); cur = []
            vias.append({"x": round(p["x"] + RK[0], 5), "y": round(p["y"] + RK[1], 5), "d": p.get("via_diameter", 0.25), "hole": p.get("via_hole_diameter", 0.15), "net": name})
            layer = p["to_layer"]
            continue
        if p["layer"] != layer:
            flush(); cur = []; layer = p["layer"]
        # a segment takes the width of its start point; where that changes (a neck-down), a new run starts at the
        # shared point so the copper stays continuous
        if len(cur) > 1 and cur[-1].get("width", 0.11) != cur[0].get("width", 0.11):
            last = cur[-1]; flush(); cur = [last]
        cur.append(p)
    flush()
for t in json.load(open(D + "/ddr.lane.routed.json"))["traces"]:
    if t["connection_name"].startswith("power_"):
        continue  # the router's copy of the supplied power fanout; the fanout itself is read below
    add(t, "DDR_" + t["connection_name"])
# a supplied fanout via must clear every RK3566 ball of another net (the supplied fanout predates the corrected ball
# map, so some of its dog-bone vias sit next to balls it took for supply balls); such a fanout is dropped and the
# ball gets a via in its own pad from fanout_bga.py instead
bxy = json.load(open(D + "/../design/rk3566-ballxy.json"))
U1_BALLS = [(bxy[b][0] + RK[0], bxy[b][1] + RK[1], n) for b, n in pins["U1"].items() if b in bxy]
BALL_R, VIA_R, GAP = 0.11, 0.125, 0.1
def clears(t, n):
    for p in t["route"]:
        if p["route_type"] != "via": continue
        x, y = p["x"] + RK[0], p["y"] + RK[1]
        for bx, by, bn in U1_BALLS:
            if bn != n and (bx - x) ** 2 + (by - y) ** 2 < (BALL_R + VIA_R + GAP) ** 2: return False
    return True
for t in json.load(open(D + "/power.fanout.json")):
    _, ref, ball = t["connection_name"].split("_", 2)
    n = pins[ref].get(ball)
    if not n or n.startswith("DDR_") or (ref == "U1" and n not in ("GND",) and not n.startswith(("VDD", "VCC"))):
        dropped.append((ref, ball, n)); continue
    if not clears(t, n):
        dropped.append((ref, ball, n + " (via too close to another net's ball)")); continue
    add(t, n)
json.dump({"traces": traces, "vias": vias}, open(D + "/fixed.json", "w"))
print("traces", len(traces), "vias", len(vias), "dropped", dropped)
