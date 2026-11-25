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
        cur.append(p)
    flush()
for t in json.load(open(D + "/ddr.lane.routed.json"))["traces"]:
    if t["connection_name"].startswith("power_"):
        continue  # the router's copy of the supplied power fanout; the fanout itself is read below
    add(t, "DDR_" + t["connection_name"])
for t in json.load(open(D + "/power.fanout.json")):
    _, ref, ball = t["connection_name"].split("_", 2)
    n = pins[ref].get(ball)
    if not n or n.startswith("DDR_") or (ref == "U1" and n not in ("GND",) and not n.startswith(("VDD", "VCC"))):
        dropped.append((ref, ball, n)); continue
    add(t, n)
json.dump({"traces": traces, "vias": vias}, open(D + "/fixed.json", "w"))
print("traces", len(traces), "vias", len(vias), "dropped", dropped)
