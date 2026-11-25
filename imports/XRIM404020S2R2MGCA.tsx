import type { InductorProps } from "@tscircuit/props"

export const XRIM404020S2R2MGCA = (props: Omit<InductorProps, "inductance">) => {
  return (
    <inductor
      inductance="2.2uH"
      supplierPartNumbers={{
  "jlcpcb": [
    "C39846857"
  ]
}}
      manufacturerPartNumber="XRIM404020S2R2MGCA"
      footprint="smdpads2_p2.6002mm_pw1.5mm_ph4.1mm_cyw4.6002mm_cyh4.61mm"
      cadModel={{
        objUrl: "https://modelcdn.tscircuit.com/easyeda_models/assets/C39846857.obj?uuid=b47977e8ec814ee8938dd0311f053b94",
        stepUrl: "https://modelcdn.tscircuit.com/easyeda_models/assets/C39846857.step?uuid=b47977e8ec814ee8938dd0311f053b94",
        pcbRotationOffset: 0,
        modelOriginPosition: { x: 0.000012700000183940574, y: -0.004999999999886429, z: -0.1 },
      }}
      {...props}
    />
  )
}