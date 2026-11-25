import type { ChipProps } from "@tscircuit/props"

const pinLabels = {
  pin1: ["BS"],
  pin2: ["GND"],
  pin3: ["FB"],
  pin4: ["EN"],
  pin5: ["IN"],
  pin6: ["LX"]
} as const

const pinAttributes = {
  pin2: {requiresGround: true}
} as const

export const SY8113BADC = (props: ChipProps<typeof pinLabels>) => {
  return (
    <chip
      pinLabels={pinLabels}
      pinAttributes={pinAttributes}
      supplierPartNumbers={{
  "jlcpcb": [
    "C78989"
  ]
}}
      manufacturerPartNumber="SY8113BADC"
      footprint={<footprint>
        <smtpad portHints={["pin1"]} pcbX="1.200023mm" pcbY="-0.94996mm" width="0.7999984mm" height="0.532003mm" shape="rect" />
<smtpad portHints={["pin2"]} pcbX="1.200023mm" pcbY="0mm" width="0.7999984mm" height="0.532003mm" shape="rect" />
<smtpad portHints={["pin3"]} pcbX="1.200023mm" pcbY="0.94996mm" width="0.7999984mm" height="0.532003mm" shape="rect" />
<smtpad portHints={["pin4"]} pcbX="-1.200023mm" pcbY="0.94996mm" width="0.7999984mm" height="0.532003mm" shape="rect" />
<smtpad portHints={["pin5"]} pcbX="-1.200023mm" pcbY="0mm" width="0.7999984mm" height="0.532003mm" shape="rect" />
<smtpad portHints={["pin6"]} pcbX="-1.200023mm" pcbY="-0.94996mm" width="0.7999984mm" height="0.532003mm" shape="rect" />
<silkscreenpath route={[{"x":0.8760714000001144,"y":1.5262098000000606},{"x":-0.8763253999999279,"y":1.5262098000000606}]} />
<silkscreenpath route={[{"x":0.8760714000001144,"y":-1.5262097999999469},{"x":-0.8763253999999279,"y":-1.5262097999999469}]} />
<silkscreencircle pcbX="1.287399mm" pcbY="-1.668526mm" radius="0.150114mm" />
<silkscreentext text="{NAME}" pcbX="0.101473mm" pcbY="2.524mm" anchorAlignment="center" fontSize="1mm" />
<courtyardoutline outline={[{"x":-1.8500222000001258,"y":1.6999844000000621},{"x":1.8500222000001258,"y":1.6999844000000621},{"x":1.8500222000001258,"y":-1.7000097999999753},{"x":-1.8500222000001258,"y":-1.7000097999999753},{"x":-1.8500222000001258,"y":1.6999844000000621}]} />
      </footprint>}
      cadModel={{
        objUrl: "https://modelcdn.tscircuit.com/easyeda_models/assets/C78989.obj?uuid=222e8593009c495bb3d3af0c08fa5e6a",
        stepUrl: "https://modelcdn.tscircuit.com/easyeda_models/assets/C78989.step?uuid=222e8593009c495bb3d3af0c08fa5e6a",
        pcbRotationOffset: 180,
        modelOriginPosition: { x: -0.0001269999999067295, y: -0.000012699999956566899, z: 0.050795 },
      }}
      {...props}
    />
  )
}