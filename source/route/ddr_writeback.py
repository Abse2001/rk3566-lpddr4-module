# Writes nets re-routed by reroute.py (board coordinates, routes.json format) back into the LPDDR4 block's
# ddr.lane.routed.json (RK3566-local coordinates), replacing each net's old trace. A via joins consecutive segments
# on different layers. Usage: ROUTES=routes.json NETS=DDR_ODT_a,... python3 ddr_writeback.py
import json, os
D = os.path.dirname(os.path.abspath(__file__)); RK = (15.2, -19.0)
rt = json.load(open(os.environ["ROUTES"]))["nets"]; R = json.load(open(D + "/ddr.lane.routed.json"))
for net in [n for n in os.environ.get("NETS", "").split(",") if n]:
    n = rt[net]; name = net[4:]
    old = [t for t in R["traces"] if t["connection_name"] == name]
    route = []; vi = 0
    for s in n["segs"]:
        if route and route[-1]["layer"] != s["layer"]:
            v = n["vias"][vi]; vi += 1
            route.append({"route_type": "via", "x": round(v["x"] - RK[0], 5), "y": round(v["y"] - RK[1], 5), "from_layer": route[-1]["layer"], "to_layer": s["layer"], "via_diameter": 0.25, "via_hole_diameter": 0.15})
        for q in s["pts"]: route.append({"route_type": "wire", "x": round(q["x"] - RK[0], 5), "y": round(q["y"] - RK[1], 5), "width": s["w"], "layer": s["layer"]})
    assert vi == len(n["vias"]), (net, vi, len(n["vias"]))
    R["traces"] = [t for t in R["traces"] if t["connection_name"] != name] + [dict(old[0], route=route)]
    print("wrote", net, len(route), "points")
json.dump(R, open(D + "/ddr.lane.routed.json", "w"))
# every wire segment carries one width at both ends: where the width changes, the change point is doubled
# (the first copy ends the old width, the second starts the new one), so no tool can read a segment wider
for t in R["traces"]:
    r = t["route"]; out = []
    for k, p in enumerate(r):
        if out and p["route_type"] == "wire" and out[-1]["route_type"] == "wire" and out[-1]["layer"] == p["layer"] and out[-1]["width"] != p["width"]:
            out.append(dict(p, width=out[-1]["width"]))
        out.append(p)
    t["route"] = out
json.dump(R, open(D + "/ddr.lane.routed.json", "w"))
