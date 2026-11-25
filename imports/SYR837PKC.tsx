import type { ChipProps } from "@tscircuit/props"

const pinLabels = {
  pin1: ["VSEL","A1"],
  pin2: ["EN","A2"],
  pin3: ["SCL","A3"],
  pin4: ["VOUT","A4"],
  pin5: ["SDA","B1"],
  pin6: ["GND1","B2"],
  pin7: ["GND2","B3"],
  pin8: ["AGND","B4"],
  pin9: ["GND3","C1"],
  pin10: ["GND4","C2"],
  pin11: ["GND5","C3"],
  pin12: ["GND6","C4"],
  pin13: ["VIN1","D1"],
  pin14: ["VIN2","D2"],
  pin15: ["SW1","D3"],
  pin16: ["SW2","D4"],
  pin17: ["VIN3","E1"],
  pin18: ["VIN4","E2"],
  pin19: ["SW3","E3"],
  pin20: ["SW4","E4"]
} as const

export const SYR837PKC = (props: ChipProps<typeof pinLabels>) => {
  return (
    <chip
      pinLabels={pinLabels}
      supplierPartNumbers={{
  "jlcpcb": [
    "C178248"
  ]
}}
      manufacturerPartNumber="SYR837PKC"
      footprint="bga20_grid5x4_p0.4mm_pad0.208mm_tlorigin_pinnumbering(columnmajor)"
      cadModel={{
        objUrl: "https://modelcdn.tscircuit.com/easyeda_models/assets/C178248.obj?uuid=f98367bdc4c144daa4b4251eadd02b99",
        stepUrl: "https://modelcdn.tscircuit.com/easyeda_models/assets/C178248.step?uuid=f98367bdc4c144daa4b4251eadd02b99",
        pcbRotationOffset: 0,
        modelOriginPosition: { x: 0.000025399999913133797, y: 0.0000762000000804619, z: 0.0500126 },
      }}
      {...props}
    />
  )
}