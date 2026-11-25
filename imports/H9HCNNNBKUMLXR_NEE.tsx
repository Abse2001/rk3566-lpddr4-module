import type { ChipProps } from "@tscircuit/props"

const pinLabels = {
  pin1: ["A1"],
  pin2: ["A2"],
  pin3: ["A3"],
  pin4: ["A4"],
  pin5: ["A5"],
  pin6: ["A8"],
  pin7: ["A9"],
  pin8: ["A10"],
  pin9: ["A11"],
  pin10: ["A12"],
  pin11: ["B1"],
  pin12: ["B2"],
  pin13: ["B3"],
  pin14: ["B4"],
  pin15: ["B5"],
  pin16: ["B8"],
  pin17: ["B9"],
  pin18: ["B10"],
  pin19: ["B11"],
  pin20: ["B12"],
  pin21: ["C1"],
  pin22: ["C2"],
  pin23: ["C3"],
  pin24: ["C4"],
  pin25: ["C5"],
  pin26: ["C8"],
  pin27: ["C9"],
  pin28: ["C10"],
  pin29: ["C11"],
  pin30: ["C12"],
  pin31: ["D1"],
  pin32: ["D2"],
  pin33: ["D3"],
  pin34: ["D4"],
  pin35: ["D5"],
  pin36: ["D8"],
  pin37: ["D9"],
  pin38: ["D10"],
  pin39: ["D11"],
  pin40: ["D12"],
  pin41: ["E1"],
  pin42: ["E2"],
  pin43: ["E3"],
  pin44: ["E4"],
  pin45: ["E5"],
  pin46: ["E8"],
  pin47: ["E9"],
  pin48: ["E10"],
  pin49: ["E11"],
  pin50: ["E12"],
  pin51: ["F1"],
  pin52: ["F2"],
  pin53: ["F3"],
  pin54: ["F4"],
  pin55: ["F5"],
  pin56: ["F8"],
  pin57: ["F9"],
  pin58: ["F10"],
  pin59: ["F11"],
  pin60: ["F12"],
  pin61: ["G1"],
  pin62: ["G2"],
  pin63: ["G3"],
  pin64: ["G4"],
  pin65: ["G5"],
  pin66: ["G8"],
  pin67: ["G9"],
  pin68: ["G10"],
  pin69: ["G11"],
  pin70: ["G12"],
  pin71: ["H1"],
  pin72: ["H2"],
  pin73: ["H3"],
  pin74: ["H4"],
  pin75: ["H5"],
  pin76: ["H8"],
  pin77: ["H9"],
  pin78: ["H10"],
  pin79: ["H11"],
  pin80: ["H12"],
  pin81: ["J1"],
  pin82: ["J2"],
  pin83: ["J3"],
  pin84: ["J4"],
  pin85: ["J5"],
  pin86: ["J8"],
  pin87: ["J9"],
  pin88: ["J10"],
  pin89: ["J11"],
  pin90: ["J12"],
  pin91: ["K1"],
  pin92: ["K2"],
  pin93: ["K3"],
  pin94: ["K4"],
  pin95: ["K5"],
  pin96: ["K8"],
  pin97: ["K9"],
  pin98: ["K10"],
  pin99: ["K11"],
  pin100: ["K12"],
  pin101: ["N1"],
  pin102: ["N2"],
  pin103: ["N3"],
  pin104: ["N4"],
  pin105: ["N5"],
  pin106: ["N8"],
  pin107: ["N9"],
  pin108: ["N10"],
  pin109: ["N11"],
  pin110: ["N12"],
  pin111: ["P1"],
  pin112: ["P2"],
  pin113: ["P3"],
  pin114: ["P4"],
  pin115: ["P5"],
  pin116: ["P8"],
  pin117: ["P9"],
  pin118: ["P10"],
  pin119: ["P11"],
  pin120: ["P12"],
  pin121: ["R1"],
  pin122: ["R2"],
  pin123: ["R3"],
  pin124: ["R4"],
  pin125: ["R5"],
  pin126: ["R8"],
  pin127: ["R9"],
  pin128: ["R10"],
  pin129: ["R11"],
  pin130: ["R12"],
  pin131: ["T1"],
  pin132: ["T2"],
  pin133: ["T3"],
  pin134: ["T4"],
  pin135: ["T5"],
  pin136: ["T8"],
  pin137: ["T9"],
  pin138: ["T10"],
  pin139: ["T11"],
  pin140: ["T12"],
  pin141: ["U1"],
  pin142: ["U2"],
  pin143: ["U3"],
  pin144: ["U4"],
  pin145: ["U5"],
  pin146: ["U8"],
  pin147: ["U9"],
  pin148: ["U10"],
  pin149: ["U11"],
  pin150: ["U12"],
  pin151: ["V1"],
  pin152: ["V2"],
  pin153: ["V3"],
  pin154: ["V4"],
  pin155: ["V5"],
  pin156: ["V8"],
  pin157: ["V9"],
  pin158: ["V10"],
  pin159: ["V11"],
  pin160: ["V12"],
  pin161: ["W1"],
  pin162: ["W2"],
  pin163: ["W3"],
  pin164: ["W4"],
  pin165: ["W5"],
  pin166: ["W8"],
  pin167: ["W9"],
  pin168: ["W10"],
  pin169: ["W11"],
  pin170: ["W12"],
  pin171: ["Y1"],
  pin172: ["Y2"],
  pin173: ["Y3"],
  pin174: ["Y4"],
  pin175: ["Y5"],
  pin176: ["Y8"],
  pin177: ["Y9"],
  pin178: ["Y10"],
  pin179: ["Y11"],
  pin180: ["Y12"],
  pin181: ["AA1"],
  pin182: ["AA2"],
  pin183: ["AA3"],
  pin184: ["AA4"],
  pin185: ["AA5"],
  pin186: ["AA8"],
  pin187: ["AA9"],
  pin188: ["AA10"],
  pin189: ["AA11"],
  pin190: ["AA12"],
  pin191: ["AB1"],
  pin192: ["AB2"],
  pin193: ["AB3"],
  pin194: ["AB4"],
  pin195: ["AB5"],
  pin196: ["AB8"],
  pin197: ["AB9"],
  pin198: ["AB10"],
  pin199: ["AB11"],
  pin200: ["AB12"]
} as const

export const H9HCNNNBKUMLXR_NEE = (props: ChipProps<typeof pinLabels>) => {
  return (
    <chip
      pinLabels={pinLabels}
      supplierPartNumbers={{
  "jlcpcb": [
    "C21912322"
  ]
}}
      manufacturerPartNumber="H9HCNNNBKUMLXR-NEE"
      footprint={<footprint>
        <smtpad portHints={["pin1"]} pcbX="-6.82498mm" pcbY="-4.400042mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin2"]} pcbX="-6.82498mm" pcbY="-3.599942mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin3"]} pcbX="-6.82498mm" pcbY="-2.800096mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin4"]} pcbX="-6.82498mm" pcbY="-1.999996mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin5"]} pcbX="-6.82498mm" pcbY="-1.199896mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin6"]} pcbX="-6.82498mm" pcbY="1.199896mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin7"]} pcbX="-6.82498mm" pcbY="1.999996mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin8"]} pcbX="-6.82498mm" pcbY="2.800096mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin9"]} pcbX="-6.82498mm" pcbY="3.599942mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin10"]} pcbX="-6.82498mm" pcbY="4.400042mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin11"]} pcbX="-6.174994mm" pcbY="-4.400042mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin12"]} pcbX="-6.174994mm" pcbY="-3.599942mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin13"]} pcbX="-6.174994mm" pcbY="-2.800096mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin14"]} pcbX="-6.174994mm" pcbY="-1.999996mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin15"]} pcbX="-6.174994mm" pcbY="-1.199896mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin16"]} pcbX="-6.174994mm" pcbY="1.199896mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin17"]} pcbX="-6.174994mm" pcbY="1.999996mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin18"]} pcbX="-6.174994mm" pcbY="2.800096mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin19"]} pcbX="-6.174994mm" pcbY="3.599942mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin20"]} pcbX="-6.174994mm" pcbY="4.400042mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin21"]} pcbX="-5.525008mm" pcbY="-4.400042mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin22"]} pcbX="-5.525008mm" pcbY="-3.599942mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin23"]} pcbX="-5.525008mm" pcbY="-2.800096mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin24"]} pcbX="-5.525008mm" pcbY="-1.999996mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin25"]} pcbX="-5.525008mm" pcbY="-1.199896mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin26"]} pcbX="-5.525008mm" pcbY="1.199896mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin27"]} pcbX="-5.525008mm" pcbY="1.999996mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin28"]} pcbX="-5.525008mm" pcbY="2.800096mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin29"]} pcbX="-5.525008mm" pcbY="3.599942mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin30"]} pcbX="-5.525008mm" pcbY="4.400042mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin31"]} pcbX="-4.875022mm" pcbY="-4.400042mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin32"]} pcbX="-4.875022mm" pcbY="-3.599942mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin33"]} pcbX="-4.875022mm" pcbY="-2.800096mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin34"]} pcbX="-4.875022mm" pcbY="-1.999996mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin35"]} pcbX="-4.875022mm" pcbY="-1.199896mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin36"]} pcbX="-4.875022mm" pcbY="1.199896mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin37"]} pcbX="-4.875022mm" pcbY="1.999996mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin38"]} pcbX="-4.875022mm" pcbY="2.800096mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin39"]} pcbX="-4.875022mm" pcbY="3.599942mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin40"]} pcbX="-4.875022mm" pcbY="4.400042mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin41"]} pcbX="-4.225036mm" pcbY="-4.400042mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin42"]} pcbX="-4.225036mm" pcbY="-3.599942mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin43"]} pcbX="-4.225036mm" pcbY="-2.800096mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin44"]} pcbX="-4.225036mm" pcbY="-1.999996mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin45"]} pcbX="-4.225036mm" pcbY="-1.199896mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin46"]} pcbX="-4.225036mm" pcbY="1.199896mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin47"]} pcbX="-4.225036mm" pcbY="1.999996mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin48"]} pcbX="-4.225036mm" pcbY="2.800096mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin49"]} pcbX="-4.225036mm" pcbY="3.599942mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin50"]} pcbX="-4.225036mm" pcbY="4.400042mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin51"]} pcbX="-3.57505mm" pcbY="-4.400042mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin52"]} pcbX="-3.57505mm" pcbY="-3.599942mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin53"]} pcbX="-3.57505mm" pcbY="-2.800096mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin54"]} pcbX="-3.57505mm" pcbY="-1.999996mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin55"]} pcbX="-3.57505mm" pcbY="-1.199896mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin56"]} pcbX="-3.57505mm" pcbY="1.199896mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin57"]} pcbX="-3.57505mm" pcbY="1.999996mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin58"]} pcbX="-3.57505mm" pcbY="2.800096mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin59"]} pcbX="-3.57505mm" pcbY="3.599942mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin60"]} pcbX="-3.57505mm" pcbY="4.400042mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin61"]} pcbX="-2.925064mm" pcbY="-4.400042mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin62"]} pcbX="-2.925064mm" pcbY="-3.599942mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin63"]} pcbX="-2.925064mm" pcbY="-2.800096mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin64"]} pcbX="-2.925064mm" pcbY="-1.999996mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin65"]} pcbX="-2.925064mm" pcbY="-1.199896mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin66"]} pcbX="-2.925064mm" pcbY="1.199896mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin67"]} pcbX="-2.925064mm" pcbY="1.999996mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin68"]} pcbX="-2.925064mm" pcbY="2.800096mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin69"]} pcbX="-2.925064mm" pcbY="3.599942mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin70"]} pcbX="-2.925064mm" pcbY="4.400042mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin71"]} pcbX="-2.275078mm" pcbY="-4.400042mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin72"]} pcbX="-2.275078mm" pcbY="-3.599942mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin73"]} pcbX="-2.275078mm" pcbY="-2.800096mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin74"]} pcbX="-2.275078mm" pcbY="-1.999996mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin75"]} pcbX="-2.275078mm" pcbY="-1.199896mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin76"]} pcbX="-2.275078mm" pcbY="1.199896mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin77"]} pcbX="-2.275078mm" pcbY="1.999996mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin78"]} pcbX="-2.275078mm" pcbY="2.800096mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin79"]} pcbX="-2.275078mm" pcbY="3.599942mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin80"]} pcbX="-2.275078mm" pcbY="4.400042mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin81"]} pcbX="-1.625092mm" pcbY="-4.400042mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin82"]} pcbX="-1.625092mm" pcbY="-3.599942mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin83"]} pcbX="-1.625092mm" pcbY="-2.800096mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin84"]} pcbX="-1.625092mm" pcbY="-1.999996mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin85"]} pcbX="-1.625092mm" pcbY="-1.199896mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin86"]} pcbX="-1.625092mm" pcbY="1.199896mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin87"]} pcbX="-1.625092mm" pcbY="1.999996mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin88"]} pcbX="-1.625092mm" pcbY="2.800096mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin89"]} pcbX="-1.625092mm" pcbY="3.599942mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin90"]} pcbX="-1.625092mm" pcbY="4.400042mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin91"]} pcbX="-0.975106mm" pcbY="-4.400042mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin92"]} pcbX="-0.975106mm" pcbY="-3.599942mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin93"]} pcbX="-0.975106mm" pcbY="-2.800096mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin94"]} pcbX="-0.975106mm" pcbY="-1.999996mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin95"]} pcbX="-0.975106mm" pcbY="-1.199896mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin96"]} pcbX="-0.975106mm" pcbY="1.199896mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin97"]} pcbX="-0.975106mm" pcbY="1.999996mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin98"]} pcbX="-0.975106mm" pcbY="2.800096mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin99"]} pcbX="-0.975106mm" pcbY="3.599942mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin100"]} pcbX="-0.975106mm" pcbY="4.400042mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin101"]} pcbX="0.975106mm" pcbY="-4.400042mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin102"]} pcbX="0.975106mm" pcbY="-3.599942mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin103"]} pcbX="0.975106mm" pcbY="-2.800096mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin104"]} pcbX="0.975106mm" pcbY="-1.999996mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin105"]} pcbX="0.975106mm" pcbY="-1.199896mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin106"]} pcbX="0.975106mm" pcbY="1.199896mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin107"]} pcbX="0.975106mm" pcbY="1.999996mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin108"]} pcbX="0.975106mm" pcbY="2.800096mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin109"]} pcbX="0.975106mm" pcbY="3.599942mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin110"]} pcbX="0.975106mm" pcbY="4.400042mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin111"]} pcbX="1.625092mm" pcbY="-4.400042mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin112"]} pcbX="1.625092mm" pcbY="-3.599942mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin113"]} pcbX="1.625092mm" pcbY="-2.800096mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin114"]} pcbX="1.625092mm" pcbY="-1.999996mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin115"]} pcbX="1.625092mm" pcbY="-1.199896mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin116"]} pcbX="1.625092mm" pcbY="1.199896mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin117"]} pcbX="1.625092mm" pcbY="1.999996mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin118"]} pcbX="1.625092mm" pcbY="2.800096mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin119"]} pcbX="1.625092mm" pcbY="3.599942mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin120"]} pcbX="1.625092mm" pcbY="4.400042mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin121"]} pcbX="2.275078mm" pcbY="-4.400042mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin122"]} pcbX="2.275078mm" pcbY="-3.599942mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin123"]} pcbX="2.275078mm" pcbY="-2.800096mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin124"]} pcbX="2.275078mm" pcbY="-1.999996mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin125"]} pcbX="2.275078mm" pcbY="-1.199896mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin126"]} pcbX="2.275078mm" pcbY="1.199896mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin127"]} pcbX="2.275078mm" pcbY="1.999996mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin128"]} pcbX="2.275078mm" pcbY="2.800096mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin129"]} pcbX="2.275078mm" pcbY="3.599942mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin130"]} pcbX="2.275078mm" pcbY="4.400042mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin131"]} pcbX="2.925064mm" pcbY="-4.400042mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin132"]} pcbX="2.925064mm" pcbY="-3.599942mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin133"]} pcbX="2.925064mm" pcbY="-2.800096mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin134"]} pcbX="2.925064mm" pcbY="-1.999996mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin135"]} pcbX="2.925064mm" pcbY="-1.199896mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin136"]} pcbX="2.925064mm" pcbY="1.199896mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin137"]} pcbX="2.925064mm" pcbY="1.999996mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin138"]} pcbX="2.925064mm" pcbY="2.800096mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin139"]} pcbX="2.925064mm" pcbY="3.599942mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin140"]} pcbX="2.925064mm" pcbY="4.400042mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin141"]} pcbX="3.57505mm" pcbY="-4.400042mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin142"]} pcbX="3.57505mm" pcbY="-3.599942mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin143"]} pcbX="3.57505mm" pcbY="-2.800096mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin144"]} pcbX="3.57505mm" pcbY="-1.999996mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin145"]} pcbX="3.57505mm" pcbY="-1.199896mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin146"]} pcbX="3.57505mm" pcbY="1.199896mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin147"]} pcbX="3.57505mm" pcbY="1.999996mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin148"]} pcbX="3.57505mm" pcbY="2.800096mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin149"]} pcbX="3.57505mm" pcbY="3.599942mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin150"]} pcbX="3.57505mm" pcbY="4.400042mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin151"]} pcbX="4.225036mm" pcbY="-4.400042mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin152"]} pcbX="4.225036mm" pcbY="-3.599942mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin153"]} pcbX="4.225036mm" pcbY="-2.800096mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin154"]} pcbX="4.225036mm" pcbY="-1.999996mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin155"]} pcbX="4.225036mm" pcbY="-1.199896mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin156"]} pcbX="4.225036mm" pcbY="1.199896mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin157"]} pcbX="4.225036mm" pcbY="1.999996mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin158"]} pcbX="4.225036mm" pcbY="2.800096mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin159"]} pcbX="4.225036mm" pcbY="3.599942mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin160"]} pcbX="4.225036mm" pcbY="4.400042mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin161"]} pcbX="4.875022mm" pcbY="-4.400042mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin162"]} pcbX="4.875022mm" pcbY="-3.599942mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin163"]} pcbX="4.875022mm" pcbY="-2.800096mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin164"]} pcbX="4.875022mm" pcbY="-1.999996mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin165"]} pcbX="4.875022mm" pcbY="-1.199896mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin166"]} pcbX="4.875022mm" pcbY="1.199896mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin167"]} pcbX="4.875022mm" pcbY="1.999996mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin168"]} pcbX="4.875022mm" pcbY="2.800096mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin169"]} pcbX="4.875022mm" pcbY="3.599942mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin170"]} pcbX="4.875022mm" pcbY="4.400042mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin171"]} pcbX="5.525008mm" pcbY="-4.400042mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin172"]} pcbX="5.525008mm" pcbY="-3.599942mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin173"]} pcbX="5.525008mm" pcbY="-2.800096mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin174"]} pcbX="5.525008mm" pcbY="-1.999996mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin175"]} pcbX="5.525008mm" pcbY="-1.199896mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin176"]} pcbX="5.525008mm" pcbY="1.199896mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin177"]} pcbX="5.525008mm" pcbY="1.999996mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin178"]} pcbX="5.525008mm" pcbY="2.800096mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin179"]} pcbX="5.525008mm" pcbY="3.599942mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin180"]} pcbX="5.525008mm" pcbY="4.400042mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin181"]} pcbX="6.174994mm" pcbY="-4.400042mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin182"]} pcbX="6.174994mm" pcbY="-3.599942mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin183"]} pcbX="6.174994mm" pcbY="-2.800096mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin184"]} pcbX="6.174994mm" pcbY="-1.999996mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin185"]} pcbX="6.174994mm" pcbY="-1.199896mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin186"]} pcbX="6.174994mm" pcbY="1.199896mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin187"]} pcbX="6.174994mm" pcbY="1.999996mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin188"]} pcbX="6.174994mm" pcbY="2.800096mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin189"]} pcbX="6.174994mm" pcbY="3.599942mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin190"]} pcbX="6.174994mm" pcbY="4.400042mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin191"]} pcbX="6.82498mm" pcbY="-4.400042mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin192"]} pcbX="6.82498mm" pcbY="-3.599942mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin193"]} pcbX="6.82498mm" pcbY="-2.800096mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin194"]} pcbX="6.82498mm" pcbY="-1.999996mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin195"]} pcbX="6.82498mm" pcbY="-1.199896mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin196"]} pcbX="6.82498mm" pcbY="1.199896mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin197"]} pcbX="6.82498mm" pcbY="1.999996mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin198"]} pcbX="6.82498mm" pcbY="2.800096mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin199"]} pcbX="6.82498mm" pcbY="3.599942mm" radius="0.1499997mm" shape="circle" />
<smtpad portHints={["pin200"]} pcbX="6.82498mm" pcbY="4.400042mm" radius="0.1499997mm" shape="circle" />
<silkscreenpath route={[{"x":-7.80478500000001,"y":-4.596180800000013},{"x":-7.80478500000001,"y":-5.304789999999997},{"x":-7.096175800000012,"y":-5.304789999999997}]} />
<silkscreenpath route={[{"x":-7.576184999999981,"y":5.076189999999997},{"x":7.5761850000000095,"y":5.076189999999997},{"x":7.5761850000000095,"y":-5.076189999999997},{"x":-7.576184999999981,"y":-5.076189999999997},{"x":-7.576184999999981,"y":5.076189999999997}]} />
<silkscreencircle pcbX="-6.800088mm" pcbY="-5.40004mm" radius="0.123698mm" />
<silkscreentext text="{NAME}" pcbX="-0.1016mm" pcbY="6.08mm" anchorAlignment="center" fontSize="1mm" />
<courtyardoutline outline={[{"x":-7.749984999999995,"y":5.249989999999997},{"x":7.749984999999995,"y":5.249989999999997},{"x":7.749984999999995,"y":-5.249990000000011},{"x":-7.749984999999995,"y":-5.249990000000011},{"x":-7.749984999999995,"y":5.249989999999997}]} />
      </footprint>}
      cadModel={{
        objUrl: "https://modelcdn.tscircuit.com/easyeda_models/assets/C21912322.obj?uuid=0db596f10c4446c19fdb3fa37027b2d7",
        stepUrl: "https://modelcdn.tscircuit.com/easyeda_models/assets/C21912322.step?uuid=0db596f10c4446c19fdb3fa37027b2d7",
        pcbRotationOffset: 0,
        modelOriginPosition: { x: 0, y: 0, z: -0.4 },
      }}
      {...props}
    />
  )
}