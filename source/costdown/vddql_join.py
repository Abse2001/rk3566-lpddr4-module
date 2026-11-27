# Joins the RK3566 DDR_VDDQL balls (1E6, 1E7, 1E9 at y -16.06; 1F5, 1G5 at x 11.65) to the VCC0V6_DDR island.
# Inside the SoC field the inner2 island cannot pass the 1.1 V DDRPHY_VDDQ row (1D5..1D9, 0.65 mm pitch), so the
# balls are chained on top in the channels between balls (0.1 mm trace, >= 0.16 mm from every ball pad) and leave
# through a via set between the D row and the GND row north of it, inside the island. check.py verifies clearance.
import json, os, sys
F = sys.argv[1]; cu = json.load(open(F + "/copper.json"))
N, W = "VCC0V6_DDR", 0.1
def tr(*pts): cu["traces"].append({"pts": [{"x": x, "y": y} for x, y in pts], "layer": "top", "w": W, "net": N})
tr((11.6548, -17.3599), (11.6548, -16.7099), (12.3048, -16.06), (12.9548, -16.06))
tr((12.9548, -16.06), (13.2798, -16.385), (13.9298, -16.385), (14.2547, -16.06))
tr((12.9548, -16.06), (13.2798, -15.735), (13.2798, -15.085))
cu["vias"].append({"x": 13.2798, "y": -15.085, "d": 0.25, "hole": 0.15, "net": N})
json.dump(cu, open(F + "/copper.json", "w")); print("added 3 traces, 1 via")
