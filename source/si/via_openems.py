# openEMS (3D FDTD) model of the module's signal via on the JLC06161H-1080A stackup, to check the via model used in
# ngspice (pair_sim.py / via_cal.py). Units mm, z = depth below the top copper (layer Z of ddr_timing.py).
#   CASE=via  : 1 mm top microstrip (0.11 mm) -> via (0.15 hole / 0.25 pad, antipads 0.55 mm on the planes it
#               passes) -> 1 mm inner3 stripline; the via continues to the bottom (0.7 mm stub, bottom pad)
#   CASE=ms   : 2 mm top microstrip        CASE=sl : 2 mm inner3 stripline   (references for the trace delays)
# Planes: inner1 GND, inner2 power (AC ground), inner4 GND, all PEC; FR-4 Er 4.2, tan d 0.02 at 5 GHz.
# Lumped 50 ohm ports at both ends between trace and its reference plane. Writes S-params (Touchstone) and the
# group delay of S21 (1-6 GHz) to si/out/<case>.*
import os, sys, numpy as np
from CSXCAD import ContinuousStructure
from openEMS import openEMS
from openEMS.physical_constants import EPS0
CASE = os.environ.get("CASE", "via"); OUT = os.path.dirname(os.path.abspath(__file__)) + "/out"; os.makedirs(OUT, exist_ok=True)
Z = {"top": 0.0, "inner1": 0.111, "inner2": 0.727, "inner3": 0.841, "inner4": 1.457, "bottom": 1.548}
W, ER, TAND, F0 = 0.11, 4.2, 0.02, 5e9
fmax = 20e9
FDTD = openEMS(NrTS=200000, EndCriteria=1e-4)
FDTD.SetGaussExcite(fmax / 2, fmax / 2)
FDTD.SetBoundaryCond(["PML_8"] * 6)
CSX = ContinuousStructure(); FDTD.SetCSX(CSX)
mesh = CSX.GetGrid(); mesh.SetDeltaUnit(1e-3)
X0, X1, Y0, Y1 = -1.6, 1.6, -0.9, 0.9
zt, zb = -Z["bottom"] - 0.6, 0.6  # air above and below (z up = -depth)
fr4 = CSX.AddMaterial("FR4", epsilon=ER, kappa=2 * np.pi * F0 * EPS0 * ER * TAND)
fr4.AddBox([X0, Y0, -Z["bottom"]], [X1, Y1, 0], priority=1)
cu = CSX.AddMetal("cu")
def plane(layer, hole=None):
    z = -Z[layer]; cu.AddBox([X0, Y0, z], [X1, Y1, z], priority=10)
    if hole is not None:  # antipad: dielectric disk cut out of the plane (higher priority)
        fr4.AddCylinder([hole[0], hole[1], z - 0.001], [hole[0], hole[1], z + 0.001], 0.275, priority=20)
VX = 0.0
if CASE == "via":
    for l in ("inner1", "inner2", "inner4"): plane(l, (VX, 0))
    cu.AddBox([X0 + 0.3, -W / 2, 0], [VX, W / 2, 0], priority=30)                            # top trace
    cu.AddBox([VX, -W / 2, -Z["inner3"]], [X1 - 0.3, W / 2, -Z["inner3"]], priority=30)     # inner3 trace
    cu.AddCylinder([VX, 0, 0], [VX, 0, -Z["bottom"]], 0.075, priority=30)                   # barrel (plated hole)
    for z in (0, -Z["inner3"], -Z["bottom"]): cu.AddCylinder([VX, 0, z], [VX, 0, z], 0.125, priority=30)  # pads
    p1 = FDTD.AddLumpedPort(1, 50, [X0 + 0.3, -W / 2, 0], [X0 + 0.3, W / 2, -Z["inner1"]], "z", 1.0, priority=40)
    p2 = FDTD.AddLumpedPort(2, 50, [X1 - 0.3, -W / 2, -Z["inner3"]], [X1 - 0.3, W / 2, -Z["inner4"]], "z", 0, priority=40)
    xs = [X0 + 0.3, VX, X1 - 0.3]
elif CASE == "ms":
    for l in ("inner1", "inner2", "inner4"): plane(l)
    cu.AddBox([X0 + 0.3, -W / 2, 0], [X1 - 0.3, W / 2, 0], priority=30)
    p1 = FDTD.AddLumpedPort(1, 50, [X0 + 0.3, -W / 2, 0], [X0 + 0.3, W / 2, -Z["inner1"]], "z", 1.0, priority=40)
    p2 = FDTD.AddLumpedPort(2, 50, [X1 - 0.3, -W / 2, 0], [X1 - 0.3, W / 2, -Z["inner1"]], "z", 0, priority=40)
    xs = [X0 + 0.3, X1 - 0.3]
else:  # sl
    for l in ("inner1", "inner2", "inner4"): plane(l)
    cu.AddBox([X0 + 0.3, -W / 2, -Z["inner3"]], [X1 - 0.3, W / 2, -Z["inner3"]], priority=30)
    p1 = FDTD.AddLumpedPort(1, 50, [X0 + 0.3, -W / 2, -Z["inner3"]], [X0 + 0.3, W / 2, -Z["inner4"]], "z", 1.0, priority=40)
    p2 = FDTD.AddLumpedPort(2, 50, [X1 - 0.3, -W / 2, -Z["inner3"]], [X1 - 0.3, W / 2, -Z["inner4"]], "z", 0, priority=40)
    xs = [X0 + 0.3, X1 - 0.3]
# mesh: fine around traces / via, graded out to the boundary
mx = sorted(set([X0, X1] + xs + [VX - 0.3, VX - 0.125, VX - 0.075, VX, VX + 0.075, VX + 0.125, VX + 0.3]))
my = [Y0, -0.3, -W / 2, 0, W / 2, 0.3, Y1]
mz = sorted(set([zt, zb] + [-v for v in Z.values()] + [-0.04, -0.4, -1.0, -1.5]))
mesh.AddLine("x", mx); mesh.AddLine("y", my); mesh.AddLine("z", mz)
mesh.SmoothMeshLines("x", 0.025, 1.3); mesh.SmoothMeshLines("y", 0.02, 1.3); mesh.SmoothMeshLines("z", 0.02, 1.3)
path = OUT + "/sim_" + CASE
FDTD.Run(path, verbose=0, cleanup=True)
f = np.linspace(0.1e9, fmax, 400)
for p in (p1, p2): p.CalcPort(path, f, ref_impedance=50)
s11 = p1.uf_ref / p1.uf_inc; s21 = p2.uf_ref / p1.uf_inc
ph = np.unwrap(np.angle(s21)); gd = -np.gradient(ph, 2 * np.pi * f)
band = (f >= 1e9) & (f <= 6e9)
with open(f"{OUT}/{CASE}.s2p", "w") as fh:
    fh.write("# Hz S RI R 50\n")
    for k in range(len(f)):
        fh.write(f"{f[k]:.0f} {s11[k].real:.6f} {s11[k].imag:.6f} {s21[k].real:.6f} {s21[k].imag:.6f} {s21[k].real:.6f} {s21[k].imag:.6f} {s11[k].real:.6f} {s11[k].imag:.6f}\n")
res = {"case": CASE, "group_delay_ps_1_6GHz": float(np.mean(gd[band]) * 1e12),
       "S11_dB_at": {g: float(20 * np.log10(abs(s11[np.argmin(abs(f - g * 1e9))]))) for g in (1, 3, 5, 10)},
       "S21_dB_at": {g: float(20 * np.log10(abs(s21[np.argmin(abs(f - g * 1e9))]))) for g in (1, 3, 5, 10)}}
import json; json.dump(res, open(f"{OUT}/{CASE}.json", "w"), indent=1); print(res)
