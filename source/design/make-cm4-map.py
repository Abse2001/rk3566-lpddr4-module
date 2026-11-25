# Builds source/design/cm4-map.json: every CM4 connector pin (1-200) -> module net, RK3566 ball where direct.
# Assignment follows the Pine64 SOQuartz (RK3566 CM4-compatible SOM); Ethernet, wireless and the eDP-on-HDMI1
# pins are not populated on this module.
import json,re,os
D=os.path.dirname(os.path.abspath(__file__))
io=json.load(open(D+'/rk3566-balls.json'))['io']
rows=json.load(open(D+'/cm4-soquartz-pins.json'))
def g(name):
    hits=[b for b,n in io.items() if any(re.fullmatch(re.escape(name)+r'(_[udz])?',part) for part in n.split('/'))]
    assert len(hits)==1,(name,hits); return hits[0]
cmname={r['pin']:r['cm4'] for r in rows}
m={}
def S(pin,net,ball=None,note=''): m[pin]={'net':net,'ball':ball,'note':note}
for p,c in cmname.items():
    if c=='GND': S(p,'GND')
    elif c.startswith('+5V'): S(p,'VCC5V0_SYS')
    elif c.startswith('CM4_3.3V'): S(p,'VCC_3V3')
    elif c.startswith('CM4_1.8V'): S(p,'VCC_1V8')
# 89/91 (WL_nDisable/BT_nDisable) only steer on-module wireless, which this module does not have
for p in [3,4,5,6,9,10,11,12,15,16,17,18,19,20,64,68,70,72,73,76,89,91,104,106,111,133,135,139,141,143,145,146,147,148,149,152,154,158,160,164,166]:
    S(p,None,note='not connected on this module')
gp={24:'GPIO3_D3',25:'GPIO3_D1',26:'GPIO3_D0',27:'GPIO3_D2',28:'GPIO3_D7',29:'GPIO3_D5',30:'GPIO3_D4',31:'GPIO3_D6',34:'GPIO4_A5',35:'GPIO1_A1',36:'GPIO1_A0',37:'GPIO4_A7',38:'GPIO4_B3',39:'GPIO4_A6',40:'GPIO4_B0',41:'GPIO4_B1',44:'GPIO4_B2',45:'GPIO4_A1',46:'GPIO4_A2',47:'GPIO4_A3',48:'GPIO4_A0',49:'GPIO3_C7',50:'GPIO3_C6',51:'GPIO0_D0',54:'GPIO4_A4',55:'GPIO0_D1',56:'GPIO4_B5',58:'GPIO4_B4',
    57:'GPIO2_A2',61:'GPIO2_A0',62:'GPIO2_A1',63:'GPIO1_D5',67:'GPIO1_D6',69:'GPIO1_D7',80:'GPIO0_B3',82:'GPIO0_B4',95:'GPIO4_C1',21:'GPIO3_B2',97:'GPIO4_C0',100:'GPIO4_B7',102:'GPIO1_B0',109:'GPIO1_B2'}
# Departures from the SOQuartz assignment: 21 (LED_nACT), 95 (LED_nPWR), 97 (Camera_GPIO) and 100 (nEXTRST) are
# plain GPIOs; they use free 3.3 V balls on the RK3566's west edge, next to J1, instead of GPIO0 balls on the east
# edge (whose routes would cross the HDMI/MIPI breakout) or, for 97, a GPIO2_C ball in the 1.8 V VCCIO4 bank.
for p,gn in gp.items(): S(p,'CM4_'+re.sub(r'[^A-Za-z0-9_]','_',cmname[p]),g(gn),gn)
phy={94:'SARADC_VIN3',96:'SARADC_VIN2',101:'USB_OTG0_ID',103:'USB_OTG0_DM',105:'USB_OTG0_DP',116:'PCIE20_RXP',118:'PCIE20_RXN',110:'PCIE20_REFCLKP',112:'PCIE20_REFCLKN',
 115:'MIPI_CSI_RX_D2N',117:'MIPI_CSI_RX_D2P',121:'MIPI_CSI_RX_D3N',123:'MIPI_CSI_RX_D3P',127:'MIPI_CSI_RX_CLK1N',129:'MIPI_CSI_RX_CLK1P',128:'MIPI_CSI_RX_D0N',130:'MIPI_CSI_RX_D0P',134:'MIPI_CSI_RX_D1N',136:'MIPI_CSI_RX_D1P',140:'MIPI_CSI_RX_CLK0N',142:'MIPI_CSI_RX_CLK0P',
 157:'MIPI_DSI_TX0_D0N',159:'MIPI_DSI_TX0_D0P',163:'MIPI_DSI_TX0_D1N',165:'MIPI_DSI_TX0_D1P',169:'MIPI_DSI_TX0_CLKN',171:'MIPI_DSI_TX0_CLKP',
 175:'MIPI_DSI_TX1_D0N',177:'MIPI_DSI_TX1_D0P',181:'MIPI_DSI_TX1_D1N',183:'MIPI_DSI_TX1_D1P',187:'MIPI_DSI_TX1_CLKN',189:'MIPI_DSI_TX1_CLKP',193:'MIPI_DSI_TX1_D2N',195:'MIPI_DSI_TX1_D2P',194:'MIPI_DSI_TX1_D3N',196:'MIPI_DSI_TX1_D3P',
 170:'HDMI_TX_D2P',172:'HDMI_TX_D2N',176:'HDMI_TX_D1P',178:'HDMI_TX_D1N',182:'HDMI_TX_D0P',184:'HDMI_TX_D0N',188:'HDMI_TX_CLKP',190:'HDMI_TX_CLKN'}
for p,n in phy.items(): S(p,n,g(n))
S(122,'PCIE20_TXP_C',note='100 nF AC coupling from PCIE20_TXP ('+g('PCIE20_TXP')+')')
S(124,'PCIE20_TXN_C',note='100 nF AC coupling from PCIE20_TXN ('+g('PCIE20_TXN')+')')
S(151,'HDMI_CEC',g('GPIO4_D1'),'HDMITX_CEC_M0')
S(153,'HDMI_HPD_PORT',note='1 kOhm to HDMI_TX_HPDIN ('+g('HDMI_TX_HPDIN')+')')
S(199,'HDMI_SDA_PORT',note='MOSFET level shifter to HDMITX_SDA ('+g('GPIO4_D0')+')')
S(200,'HDMI_SCL_PORT',note='MOSFET level shifter to HDMITX_SCL ('+g('GPIO4_C7')+')')
S(75,'SD_PWR_ON',g('GPIO3_A4'),'GPIO3_A4 (3.3 V) with 10 kOhm pull-up: SD power on by default, software can power-cycle the card')
S(78,'VCCIO6',note='GPIO bank voltage supplied by the carrier (RK3566 VCCIO6)')
S(92,'RESETn',note='RK809 RESETB, RK3566 nPOR')
S(93,'CM4_nRPIBOOT',note='1 kOhm to EMMC_CLK (GPIO1_C5, 1.8 V): grounding it forces maskrom/USB boot; the resistor limits the current if a carrier drives this pin at 3.3 V')
S(99,'EN_3V3',note='GLOBAL_EN: enable of the 5 V -> 3.3 V buck that feeds the RK809 (100 kOhm pull-up to 5 V, as on a CM4); low keeps the module off')
miss=[p for p in range(1,201) if p not in m]; assert not miss, miss
json.dump({str(k):dict(v,cm4=cmname[k]) for k,v in sorted(m.items())},open(D+'/cm4-map.json','w'),indent=1)
from collections import Counter
print('pins',len(m),Counter('NC' if v['net'] is None else ('power' if v['net'] in ('GND','VCC5V0_SYS','VCC_3V3','VCC_1V8') else 'signal') for v in m.values()))
