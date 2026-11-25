import type { InductorProps } from "@tscircuit/props"

export const WIP252012P_R47ML = (props: Omit<InductorProps, "inductance">) => {
  return (
    <inductor
      inductance="470nH"
      supplierPartNumbers={{
  "jlcpcb": [
    "C964119"
  ]
}}
      manufacturerPartNumber="WIP252012P-R47ML"
      footprint="smdpads2_p2.2001mm_pw1mm_ph2mm_cyw3.7001mm_cyh2.5mm_pin1location(rightside,top)"
      cadModel={{
        objUrl: "https://modelcdn.tscircuit.com/easyeda_models/assets/C964119.obj?uuid=cbafd8cbc37c4463a29cf9e1710baa4a",
        stepUrl: "https://modelcdn.tscircuit.com/easyeda_models/assets/C964119.step?uuid=cbafd8cbc37c4463a29cf9e1710baa4a",
        pcbRotationOffset: 0,
        modelOriginPosition: { x: 0, y: 0, z: -0.01 },
      }}
      {...props}
    />
  )
}