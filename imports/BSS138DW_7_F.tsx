import type { ChipProps } from "@tscircuit/props"

const pinLabels = {
  pin1: ["S2"],
  pin2: ["G2"],
  pin3: ["D1"],
  pin4: ["S1"],
  pin5: ["G1"],
  pin6: ["D2"]
} as const

export const BSS138DW_7_F = (props: ChipProps<typeof pinLabels>) => {
  return (
    <chip
      pinLabels={pinLabels}
      supplierPartNumbers={{
  "jlcpcb": [
    "C154900"
  ]
}}
      manufacturerPartNumber="BSS138DW-7-F"
      footprint="dfn6_p0.65mm_w2.6802mm_pw0.35mm_pl0.78mm"
      cadModel={{
        objUrl: "https://modelcdn.tscircuit.com/easyeda_models/assets/C154900.obj?uuid=e8c049de0bbc469ba32d5592f1765e02",
        stepUrl: "https://modelcdn.tscircuit.com/easyeda_models/assets/C154900.step?uuid=e8c049de0bbc469ba32d5592f1765e02",
        pcbRotationOffset: 0,
        modelOriginPosition: { x: 0.000012699999999199463, y: 0, z: -0.1 },
      }}
      {...props}
    />
  )
}