import type { ChipProps } from "@tscircuit/props"

const pinLabels = {
  pin1: ["pin1"],
  pin2: ["pin2"]
} as const

export const HCB1005KF_121T20 = (props: ChipProps<typeof pinLabels>) => {
  return (
    <chip
      pinLabels={pinLabels}
      symbol={
        <symbol>
          <port name="pin2" pinNumber={2} aliases={["2"]} direction="right" schX={0.4} schY={0} schStemLength={0.06} />
          <port name="pin1" pinNumber={1} aliases={["1"]} direction="left" schX={-0.4} schY={0} schStemLength={0.06} />
          <schematicpath svgPath="M -0.33766 0.00136 A 0.08 0.078 0 1 0 -0.17836 0.00128" strokeColor="#880000" />
          <schematicpath svgPath="M -0.168 0.00142 A 0.08 0.078 0 1 0 -0.0087 0.00132" strokeColor="#880000" />
          <schematicpath svgPath="M 0.00134 0.00142 A 0.08 0.078 0 1 0 0.16064 0.00132" strokeColor="#880000" />
          <schematicpath svgPath="M 0.174 0.00138 A 0.08 0.078 0 1 0 0.3333 0.00128" strokeColor="#880000" />
          <schematictext schX={0} schY={0.286} text="{NAME}" fontSize={0.2} anchor="bottom_center" />
        </symbol>
      }
      supplierPartNumbers={{
  "jlcpcb": [
    "C141722"
  ]
}}
      manufacturerPartNumber="HCB1005KF-121T20"
      footprint="smdpads2_p0.84mm_pw0.54mm_ph0.54mm_cyw1.88mm_cyh1.04mm"
      cadModel={{
        objUrl: "https://modelcdn.tscircuit.com/easyeda_models/assets/C141722.obj?uuid=c498e8771bc24312a11c6413631665a8",
        stepUrl: "https://modelcdn.tscircuit.com/easyeda_models/assets/C141722.step?uuid=c498e8771bc24312a11c6413631665a8",
        pcbRotationOffset: 0,
        modelOriginPosition: { x: 0, y: -0.000012700000070253736, z: -0.25 },
      }}
      {...props}
    />
  )
}