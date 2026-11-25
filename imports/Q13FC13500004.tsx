import type { CrystalProps } from "@tscircuit/props"

type ImportedCrystalProps = Omit<CrystalProps, "frequency" | "pinVariant">

export const Q13FC13500004 = (props: ImportedCrystalProps) => {
  const { name = "X1", ...restProps } = props

  return (
    <crystal
      name={name}
      frequency="32.768kHz"
      pinVariant="two_pin"
      supplierPartNumbers={{
  "jlcpcb": [
    "C32346"
  ]
}}
      manufacturerPartNumber="Q13FC13500004"
      footprint="smdpads2_p2.5001mm_pw1mm_ph1.8mm_cyw4.0001mm_cyh2.3mm"
      cadModel={{
        objUrl: "https://modelcdn.tscircuit.com/easyeda_models/assets/C32346.obj?uuid=fd4574cdfbe94d00a9458103bda2310c",
        stepUrl: "https://modelcdn.tscircuit.com/easyeda_models/assets/C32346.step?uuid=fd4574cdfbe94d00a9458103bda2310c",
        pcbRotationOffset: 0,
        modelOriginPosition: { x: 0, y: -0.0001396999999911941, z: 0 },
      }}
      {...restProps}
    />
  )
}