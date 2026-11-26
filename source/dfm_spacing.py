# Component-to-component spacing against JLCPCB's "minimum spacing for SMD components" table (mm), same side only.
# Distance is measured edge to edge between each part's extent = union of its pads and its nominal body
# (chip passives: 0201 0.6x0.3, 0402 1.0x0.5, 0603 1.6x0.8, 0805 2.0x1.25; ICs: pcb_component width/height).
import json, sys, itertools, os
from shapely.geometry import box
from shapely.ops import unary_union
from shapely import affinity
D = os.path.dirname(os.path.abspath(__file__))
cj = json.load(open(sys.argv[1] if len(sys.argv) > 1 else D + "/../index.circuit.json"))
net = json.load(open(D + "/design/netlist.json")); roles = json.load(open(D + "/design/roles.json"))
role = {c["ref"]: c["role"] for c in net["components"]}
src = {e["source_component_id"]: e for e in cj if e["type"] == "source_component"}
BODY = {"0201": (0.6, 0.3), "0402": (1.0, 0.5), "0603": (1.6, 0.8), "0805": (2.0, 1.25), "1206": (3.2, 1.6)}
# datasheet bodies (L along the pad axis x W) of the non-chip parts; ICs without an entry use their pad extent
PBODY = {"WIP252012P-R47ML": (2.5, 2.0), "TFM252012ALMAR22MTAA": (2.5, 2.0), "XRIM404020S2R2MGCA": (4.0, 4.0),
         "XL2EL89COI-111YLC-24M": (2.5, 2.0), "Q13FC13500004": (3.2, 1.5), "HCB1005KF-121T20": (1.0, 0.5),
         "SY8113BADC": (2.9, 1.6), "BSS138DW-7-F": (2.0, 1.25), "SYR837PKC": (2.0, 1.6)}
KIND = {"U1": "BGA", "U2": "BGA", "U6": "BGA", "U4": "BGA", "U3": "QFN", "U5": "SOT", "Q1": "SOT", "J1": "CONN", "J2": "CONN"}
RULE = {("chip", "chip"): 0.15, ("chip", "BGA"): 1.0, ("chip", "QFN"): 1.0, ("chip", "SOT"): 0.2, ("BGA", "BGA"): 2.0, ("BGA", "QFN"): 1.5, ("BGA", "SOT"): 1.0, ("QFN", "SOT"): 1.0}
def rule(a, b):
    k = (a, b) if (a, b) in RULE else (b, a)
    return RULE.get(k, 0.3)
parts = []
for c in (e for e in cj if e["type"] == "pcb_component"):
    s = src.get(c["source_component_id"])
    if not s: continue
    ref = s["name"]; fp = roles.get(role.get(ref, ""), {}).get("fp") if isinstance(roles.get(role.get(ref, "")), dict) else None
    pads = [e for e in cj if e["type"] == "pcb_smtpad" and e["pcb_component_id"] == c["pcb_component_id"]]
    g = []
    for p in pads:
        if p["shape"] == "circle": w = h = 2 * p["radius"]
        else: w, h = p["width"], p["height"]
        if p["shape"] == "rotated_rect" and round(p.get("ccw_rotation", 0)) % 180 == 90: w, h = h, w
        g.append(box(p["x"] - w / 2, p["y"] - h / 2, p["x"] + w / 2, p["y"] + h / 2))
    kind = KIND.get(ref, "chip" if fp in BODY else "other")
    if fp in BODY:
        L, W = BODY[fp]; b = affinity.rotate(box(-L / 2, -W / 2, L / 2, W / 2), c["rotation"]); g.append(affinity.translate(b, c["center"]["x"], c["center"]["y"]))
    elif s.get("manufacturer_part_number") in PBODY:
        L, W = PBODY[s["manufacturer_part_number"]]; bx = unary_union(g).bounds  # orient the body along the longer pad extent
        if (bx[3] - bx[1]) > (bx[2] - bx[0]): L, W = W, L
        if s["manufacturer_part_number"] in ("SY8113BADC", "BSS138DW-7-F", "SYR837PKC"): L, W = (W, L) if c["rotation"] % 180 else (L, W)
        g.append(box(c["center"]["x"] - L / 2, c["center"]["y"] - W / 2, c["center"]["x"] + L / 2, c["center"]["y"] + W / 2))
    elif c.get("width"): g.append(box(c["center"]["x"] - c["width"] / 2, c["center"]["y"] - c["height"] / 2, c["center"]["x"] + c["width"] / 2, c["center"]["y"] + c["height"] / 2))
    parts.append((ref, c["layer"], kind, unary_union(g), unary_union(g[:len(pads)])))
viol = []
pp = []
for (r1, l1, k1, g1, p1), (r2, l2, k2, g2, p2) in itertools.combinations(parts, 2):
    if l1 != l2: continue
    if p1.distance(p2) < 0.15 - 1e-6: pp.append((round(p1.distance(p2), 3), r1, r2, l1))
    need = rule(k1, k2); d = g1.distance(g2)
    if d < need - 1e-6: viol.append((round(d, 3), need, r1, k1, r2, k2, l1))
viol.sort()
from collections import Counter
print(len(viol), "pairs below JLCPCB's recommended spacing;", Counter((v[3], v[5], v[6]) for v in viol))
for v in viol[:int(os.environ.get("N", 40))]: print(" ", v)
print(len(pp), "pad pairs of different parts closer than 0.15 mm (any net):", sorted(pp)[:20])
