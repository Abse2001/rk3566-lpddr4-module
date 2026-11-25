# Builds source/design/netlist.json: every component of the RK3566 module and every pin's net.
#
# Sources: rk3566-balls.json (RK3566 datasheet ball map), cm4-map.json (CM4 connector assignment), rails.py
# (power tree), ../route/ddr.input.json (the routed LPDDR4 nets) and ../route/power.meta.json (LPDDR4 power
# balls). Circuit details follow the Pine64 SOQuartz v1.1 schematic and the RK3566 hardware design guide.
# Component values refer to roles in parts.json (role -> LCSC part).
import json, os, re, sys
D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D)
import rails

balls = json.load(open(D + "/rk3566-balls.json"))
io, pw = balls["io"], balls["power"]
cm4 = json.load(open(D + "/cm4-map.json"))
ddr = json.load(open(D + "/../route/ddr.input.json"))
pmeta = json.load(open(D + "/../route/power.meta.json"))

comps = []  # {ref, role, value, pins: {pin: net}, group}
def comp(ref, role, pins, value="", group=""):
    comps.append({"ref": ref, "role": role, "value": value, "pins": pins, "group": group})
    return ref
_n = {"R": 0, "C": 0, "L": 0}
def nxt(k):
    _n[k] += 1
    return f"{k}{_n[k]}"
def R(a, b, value, role=None, group=""):
    return comp(nxt("R"), role or "R_" + value, {"1": a, "2": b}, value, group)
def C(a, b, value, role=None, group=""):
    return comp(nxt("C"), role or "C_" + value, {"1": a, "2": b}, value, group)
def L(a, b, value, role, group=""):
    return comp(nxt("L"), role, {"1": a, "2": b}, value, group)

def ball(name):
    hits = [b for b, n in io.items() if any(re.fullmatch(re.escape(name) + r"(_[udz])?", p) for p in n.split("/"))]
    assert len(hits) == 1, (name, hits)
    return hits[0]

# ---------------- U1 RK3566 ----------------
u1 = {}
for b, g in pw.items():
    u1[b] = rails.RK3566[g]
for c in ddr["connections"]:  # routed LPDDR4 nets
    for p in c["pointsToConnect"]:
        if p["pointId"].startswith("U1_"):
            u1[p["pointId"][3:]] = "DDR_" + c["name"]
for pin, v in cm4.items():
    if v["ball"]:
        u1[v["ball"]] = v["net"]
SIG = {
    # eMMC (VCCIO2 = 1.8 V)
    "EMMC_D0": "EMMC_D0", "EMMC_D1": "EMMC_D1", "EMMC_D2": "EMMC_D2", "EMMC_D3": "EMMC_D3",
    "EMMC_D4": "EMMC_D4", "EMMC_D5": "EMMC_D5", "EMMC_D6": "EMMC_D6", "EMMC_D7": "EMMC_D7",
    "EMMC_CMD": "EMMC_CMD", "EMMC_CLKOUT": "EMMC_CLK", "EMMC_DATA_STROBE": "EMMC_DS", "EMMC_RSTn": "EMMC_RSTN",
    # PMIC
    "I2C0_SCL": "I2C0_SCL", "I2C0_SDA": "I2C0_SDA", "PMIC_SLEEP": "PMIC_SLEEP", "GPIO0_A3": "PMIC_INT_L",
    "CLK32K_IN": "CLK32K", "nPOR": "RESETn", "TSADC_SHUT_M0": "RESETn", "FLASH_VOL_SEL": "FLASH_VOL_SEL",
    # clocks, PHY support
    "XIN24M": "XIN24M", "XOUT24M": "XOUT24M_R", "DDR_RZQ": "DDR_RZQ", "HDMI_TX_REXT": "HDMI_TX_REXT",
    "HDMI_TX_HPDIN": "HDMI_TX_HPDIN", "HDMITX_SCL": "HDMITX_SCL", "HDMITX_SDA": "HDMITX_SDA",
    "PCIE20_TXP": "PCIE20_TXP", "PCIE20_TXN": "PCIE20_TXN", "USB_OTG0_VBUSDET": "USB_OTG0_VBUSDET",
}
for name, net in SIG.items():
    u1[ball(name)] = net
for b in io:
    u1.setdefault(b, None)  # unused IO: not connected
comp("U1", "RK3566", u1, group="soc")

# ---------------- U2 LPDDR4 ----------------
u2 = {}
for c in ddr["connections"]:
    for p in c["pointsToConnect"]:
        if p["pointId"].startswith("U2_"):
            u2[p["pointId"][3:]] = "DDR_" + c["name"]
for c in pmeta["powerConnections"]:
    if c["name"].startswith("power_U2_"):
        b, n = c["name"][9:], c["netConnectionName"]
        u2[b] = "LPDDR4_ZQ0" if n == "ZQ0" else rails.LPDDR4[n]
comp("U2", "LPDDR4", u2, group="soc")  # balls not listed are NC/DNU on this x32 2-channel part
R("LPDDR4_ZQ0", "VCC_DDR", "240R", "R_240R_1%", "soc")  # LPDDR4 ZQ to VDDQ
R("DDR_RZQ", "GND", "120R", "R_120R_1%", "soc")         # RK3566 DDR PHY calibration (SOQuartz sheet 9 R1)
R("HDMI_TX_REXT", "GND", "1.62k", "R_1K62_1%", "soc")    # SOQuartz R27

# ---------------- clocks ----------------
comp("Y1", "XTAL_24M", {"1": "XIN24M", "3": "XOUT24M", "2": "GND", "4": "GND"}, "24MHz", "clock")
C("XIN24M", "GND", "18pF", "C_18P", "clock")
C("XOUT24M", "GND", "18pF", "C_18P", "clock")
R("XIN24M", "XOUT24M", "1M", "R_1M", "clock")
R("XOUT24M", "XOUT24M_R", "22R", "R_22R", "clock")

# ---------------- eMMC (VCC 3.3 V, VCCQ 1.8 V) ----------------
comp("U6", "EMMC", {"VCC": "VCC_3V3", "VCCQ": "VCC_1V8", "VSS": "GND", "VSSQ": "GND", "VDDI": "EMMC_VDDI",
     "CLK": "EMMC_CLK", "CMD": "EMMC_CMD", "DS": "EMMC_DS", "RST_n": "EMMC_RSTN",
     **{f"DAT{i}": f"EMMC_D{i}" for i in range(8)}}, group="emmc")
C("EMMC_VDDI", "GND", "1uF", "C_1U_0201", "emmc")
for v, n in (("VCC_3V3", 2), ("VCC_1V8", 3)):
    for _ in range(n):
        C(v, "GND", "100nF", "C_100N_0201", "emmc")
    C(v, "GND", "4.7uF", "C_4U7_0402", "emmc")
R("EMMC_CMD", "VCC_1V8", "10k", "R_10K", "emmc")
R("EMMC_RSTN", "VCC_1V8", "10k", "R_10K", "emmc")
R("EMMC_D0", "VCC_1V8", "10k", "R_10K", "emmc")

# ---------------- RK809-5 PMIC ----------------
SYS = "VCC3V3_SYS"
u3 = {"VCC1": SYS, "VCC2": SYS, "VCC3": SYS, "VCC4": SYS, "VCC5": SYS, "VCC6": SYS, "VCC7": SYS, "VCC8": SYS, "VCC9": SYS,
      "SW1": "SW1", "FB1": "FB1", "SW2": "SW2", "FB2": "FB2", "SW3": "SW3", "VBUCK3": "VCC_DDR", "FB3": "FB3",
      "SW4": "SW4", "FB4": "FB4", "SW5": "SW5", "FB5": "VCC_1V8",
      "LDO1": "VDDA0V9_IMAGE", "LDO2": "VDDA_0V9", "LDO3": "VDDA0V9_PMU", "LDO4": "VCCIO_ACODEC", "LDO5": "VCCIO_SD",
      "LDO6": "VCC3V3_PMU", "LDO7": "VCCA_1V8", "LDO8": "VCCA1V8_PMU", "LDO9": "VCCA1V8_IMAGE",
      "SWOUT1": "VCC_3V3", "SWOUT2": "VCC3V3_SD",
      "VREF": "RK809_VREF", "GNDREF": "GND", "EP": "GND", "VCC_RTC": SYS, "BATDIV": "RK809_BATDIV",
      "SNSP": "GND", "SNSN": "GND", "EXT_EN": None, "VDC": "RK809_VDC",
      "XIN": "RK809_XIN", "XOUT": "RK809_XOUT", "SDA": "I2C0_SDA", "SCL": "I2C0_SCL", "INT": "PMIC_INT_L",
      "SLEEP": "PMIC_SLEEP", "CLK32K": "RK809_CLK32K", "RESETB": "RESETn", "PWRON": "PMIC_PWRON",
      # audio codec unused: its supplies still need their decoupling
      "VCC_1P8D": "RK809_1P8D", "VCC_1P8A": "RK809_1P8A", "VCC_SPK_HP": "RK809_SPK_HP",
      "VCC_CPVDD": "RK809_CPVDD", "VCC_CPVSS": "RK809_CPVSS", "CPP": None, "CPN": None,
      "SPKP_OUT": None, "SPKN_OUT": None, "HPL_OUT": None, "HPR_OUT": None, "HP_SNS": "GND",
      "MICIN": None, "MICIP": None, "LRCLK": None, "BCLK": None, "MCLK": None, "SDI": None, "SDO": None, "PDMCLK": None}
comp("U3", "RK809", u3, group="pmic")
for _ in range(2): C(SYS, "GND", "22uF", "C_22U_0603", "pmic")   # VCC1, VCC2
for _ in range(2): C(SYS, "GND", "10uF", "C_10U_0603", "pmic")   # VCC3, VCC4
for _ in range(5): C(SYS, "GND", "1uF", "C_1U_0201", "pmic")     # VCC5..VCC8, VCC_RTC
C(SYS, "GND", "10uF", "C_10U_0402", "pmic")                       # VCC9
BUCK = {1: "VDD_LOGIC", 2: "VDD_GPU", 4: "VDD_NPU"}
for k, rail in BUCK.items():  # remote-sensed 0.9 V bucks: FB from the SoC with 100 R to the local output
    L(f"SW{k}", rail, "470nH", "L_470N", "pmic")
    C(rail, "GND", "22uF", "C_22U_0603", "pmic"); C(rail, "GND", "10uF", "C_10U_0402", "pmic"); C(rail, "GND", "100nF", "C_100N_0201", "pmic")
    R(rail, f"FB{k}", "100R", "R_100R", "pmic")
L("SW3", "VCC_DDR", "470nH", "L_470N", "pmic")
C("VCC_DDR", "GND", "22uF", "C_22U_0603", "pmic"); C("VCC_DDR", "GND", "10uF", "C_10U_0402", "pmic")
R("VCC_DDR", "FB3", "47k", "R_47K_1%", "pmic"); R("FB3", "GND", "120k", "R_120K_1%", "pmic")  # 1.1 V for LPDDR4
L("SW5", "VCC_1V8", "470nH", "L_470N", "pmic")
C("VCC_1V8", "GND", "22uF", "C_22U_0603", "pmic"); C("VCC_1V8", "GND", "10uF", "C_10U_0402", "pmic"); C("VCC_1V8", "GND", "10uF", "C_10U_0402", "pmic")
for rail in ("VDDA0V9_IMAGE", "VDDA_0V9", "VDDA0V9_PMU", "VCCIO_ACODEC", "VCCIO_SD", "VCC3V3_PMU", "VCCA_1V8", "VCCA1V8_PMU", "VCCA1V8_IMAGE", "VCC3V3_SD"):
    C(rail, "GND", "1uF", "C_1U_0201", "pmic")
C("VCC_3V3", "GND", "10uF", "C_10U_0402", "pmic")
C("RK809_VREF", "GND", "1uF", "C_1U_0201", "pmic")
R("RK809_BATDIV", "GND", "20k", "R_20K_1%", "pmic")
R("VCC5V0_SYS", "RK809_VDC", "47k", "R_47K", "pmic"); R("RK809_VDC", "GND", "20k", "R_20K", "pmic"); C("RK809_VDC", "GND", "10nF", "C_10N_0201", "pmic")
C("VCC5V0_SYS", "GND", "10uF", "C_10U_0402", "pmic")
C("PMIC_PWRON", "GND", "100nF", "C_100N_0201", "pmic")
C("RESETn", "GND", "100nF", "C_100N_0201", "pmic"); R("RESETn", "VCC3V3_PMU", "10k", "R_10K", "pmic")
comp("Y2", "XTAL_32K", {"1": "RK809_XIN", "2": "RK809_XOUT"}, "32.768kHz", "pmic")
C("RK809_XIN", "GND", "18pF", "C_18P", "pmic"); C("RK809_XOUT", "GND", "18pF", "C_18P", "pmic")
R("RK809_CLK32K", "VCC3V3_PMU", "10k", "R_10K", "pmic")  # CLK32K is open drain
R("RK809_CLK32K", "CLK32K", "22R", "R_22R", "pmic")
R("I2C0_SCL", "VCC3V3_PMU", "2.2k", "R_2K2", "pmic"); R("I2C0_SDA", "VCC3V3_PMU", "2.2k", "R_2K2", "pmic")
for n in ("RK809_1P8D", "RK809_1P8A", "RK809_CPVDD", "RK809_CPVSS"):
    C(n, "GND", "1uF", "C_1U_0201", "pmic")
comp("FB1", "FERRITE_120R", {"1": "VCC5V0_SYS", "2": "RK809_SPK_HP"}, "120R@100MHz", "pmic")
C("RK809_SPK_HP", "GND", "10uF", "C_10U_0402", "pmic")  # VCC_SPK_HP
R("FLASH_VOL_SEL", "VCC3V3_PMU", "10k", "R_10K", "pmic")  # eMMC at 1.8 V

# ---------------- VDD_CPU buck (role BUCK_CPU, pins named in parts.json) and 3.3 V buck ----------------
comp("U4", "BUCK_CPU", {"VIN": "VCC5V0_SYS", "SW": "SW_CPU", "VOUT": "CPU_FB", "EN": "CPU_EN", "VSEL": "CPU_VSEL",
     "SDA": "CPU_SDA", "SCL": "CPU_SCL", "AGND": "GND", "GND": "GND"}, group="cpu")
L("SW_CPU", "VDD_CPU", "0.22uH", "L_CPU", "cpu")
C("VCC5V0_SYS", "GND", "22uF", "C_22U_0805_25V", "cpu"); C("VCC5V0_SYS", "GND", "10uF", "C_10U_0603_25V", "cpu"); C("VCC5V0_SYS", "GND", "100nF", "C_100N_0201", "cpu")
for _ in range(2): C("VDD_CPU", "GND", "22uF", "C_22U_0603", "cpu")
C("VDD_CPU", "GND", "100nF", "C_100N_0201", "cpu")
R("CPU_EN", "VCC3V3_PMU", "51k", "R_51K", "cpu")
R("PMIC_SLEEP", "CPU_VSEL", "22R", "R_22R", "cpu")
R("I2C0_SDA", "CPU_SDA", "22R", "R_22R", "cpu"); R("I2C0_SCL", "CPU_SCL", "22R", "R_22R", "cpu")
R("VDD_CPU", "CPU_FB", "100R", "R_100R", "cpu")  # output sense, taken at the SoC balls
comp("U5", "BUCK_3V3", {"IN": "VCC5V0_SYS", "LX": "SW_3V3", "BS": "BS_3V3", "FB": "FB_3V3", "EN": "EN_3V3", "GND": "GND"}, group="sys")
L("SW_3V3", SYS, "2.2uH", "L_3V3", "sys")
C("BS_3V3", "SW_3V3", "100nF", "C_100N_0402_50V", "sys")
C("VCC5V0_SYS", "GND", "10uF", "C_10U_0603_25V", "sys"); C("VCC5V0_SYS", "GND", "22uF", "C_22U_0805_25V", "sys"); C("VCC5V0_SYS", "GND", "100nF", "C_100N_0402", "sys")
for _ in range(2): C(SYS, "GND", "22uF", "C_22U_0603", "sys")
C(SYS, "GND", "100nF", "C_100N_0402", "sys")
R(SYS, "FB_3V3", "100k", "R_100K_1%", "sys"); R("FB_3V3", "GND", "22k", "R_22K_1%", "sys")  # 0.6 V x (1 + 100/22) = 3.33 V
C(SYS, "FB_3V3", "22pF", "C_22P", "sys")
R("VCC5V0_SYS", "EN_3V3", "100k", "R_100K_1%", "sys")

# ---------------- RK3566 decoupling (SOQuartz sheet 8 and the IO/analog sheets) ----------------
for rail, caps in {"VDD_CPU": ["100nF", "100nF", "10uF", "10uF"], "VDD_LOGIC": ["100nF", "100nF", "10uF", "10uF"],
                   "VDD_GPU": ["100nF", "100nF", "10uF", "10uF"], "VDD_NPU": ["100nF", "100nF", "10uF", "10uF"],
                   "VCC_DDR": ["100nF"] * 8 + ["10uF", "10uF"]}.items():
    for v in caps:
        C(rail, "GND", v, "C_100N_0201" if v == "100nF" else "C_10U_0402", "decap")
for g in sorted(set(pw.values())):
    net = rails.RK3566[g]
    if net in ("GND", "VDD_CPU", "VDD_LOGIC", "VDD_GPU", "VDD_NPU", "VCC_DDR"):
        continue
    C(net, "GND", "100nF", "C_100N_0201", "decap")  # one per supply group, at its balls
for rail in ("VDDA_0V9", "VCCA_1V8", "VCC_1V8", "VCC_3V3", "VDDA0V9_PMU", "VCC3V3_PMU", "VCCIO6"):
    C(rail, "GND", "1uF", "C_1U_0201", "decap")
for _ in range(4): C("VCC_DDR", "GND", "100nF", "C_100N_0201", "decap")  # LPDDR4 VDD2/VDDQ
C("VCCA1V8_PMU", "GND", "100nF", "C_100N_0201", "decap"); C("VCCA1V8_PMU", "GND", "1uF", "C_1U_0201", "decap")  # LPDDR4 VDD1

# ---------------- interface support ----------------
C("PCIE20_TXP", "PCIE20_TXP_C", "100nF", "C_100N_0201", "io"); C("PCIE20_TXN", "PCIE20_TXN_C", "100nF", "C_100N_0201", "io")
R("HDMI_TX_HPDIN", "HDMI_HPD_PORT", "1k", "R_1K", "io")
comp("Q1", "NMOS_DUAL", {"G1": "VCC_3V3", "S1": "HDMITX_SCL", "D1": "HDMI_SCL_PORT", "G2": "VCC_3V3", "S2": "HDMITX_SDA", "D2": "HDMI_SDA_PORT"}, group="io")
R("HDMITX_SCL", "VCC_3V3", "2.2k", "R_2K2", "io"); R("HDMITX_SDA", "VCC_3V3", "2.2k", "R_2K2", "io")
R("HDMI_SCL_PORT", "VCC5V0_SYS", "1.8k", "R_1K8", "io"); R("HDMI_SDA_PORT", "VCC5V0_SYS", "1.8k", "R_1K8", "io")
R("SD_PWR_ON", "VCC_3V3", "10k", "R_10K", "io")
R("USB_OTG0_VBUSDET", "VCC_3V3", "10k", "R_10K", "io")  # always report VBUS (CM4 has no VBUS sense pin)

# ---------------- connectors (CM4 pinout, pins 1-100 on J1, 101-200 on J2) ----------------
for ref, lo in (("J1", 1), ("J2", 101)):
    comp(ref, "DF40_HEADER", {str(p - lo + 1): cm4[str(p)]["net"] for p in range(lo, lo + 100)}, group="conn")

# ---------------- sanity ----------------
nets = {}
for c in comps:
    for p, n in c["pins"].items():
        if n:
            nets.setdefault(n, []).append(f"{c['ref']}.{p}")
single = sorted(n for n, v in nets.items() if len(v) == 1)
json.dump({"components": comps, "nets": nets}, open(D + "/netlist.json", "w"), indent=0)
from collections import Counter
print("components", len(comps), Counter(c["ref"][0] for c in comps), "nets", len(nets))
print("single-pin nets (check):", single)
