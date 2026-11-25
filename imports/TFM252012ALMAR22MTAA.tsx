import type { InductorProps } from "@tscircuit/props"

export const TFM252012ALMAR22MTAA = (props: Omit<InductorProps, "inductance">) => {
  return (
    <inductor
      inductance="220nH"
      supplierPartNumbers={{
  "jlcpcb": [
    "C404798"
  ]
}}
      manufacturerPartNumber="TFM252012ALMAR22MTAA"
      footprint="smdpads2_p2.0564mm_pw1.2mm_ph2.2mm_cyw3.7564mm_cyh2.7mm_pin1location(rightside,top)"
      cadModel={{
        objUrl: "https://modelcdn.tscircuit.com/easyeda_models/assets/C404798.obj?uuid=31c78ce47d6348f68c39f00fe49916a1",
        stepUrl: "https://modelcdn.tscircuit.com/easyeda_models/assets/C404798.step?uuid=31c78ce47d6348f68c39f00fe49916a1",
        pcbRotationOffset: 0,
        modelOriginPosition: { x: 0, y: 0, z: 0 },
      }}
      {...props}
    />
  )
}