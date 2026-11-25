// Component factory shared by the probe and the board build: role -> tscircuit element.
import { RK3566 } from "../imports/RK3566"
import { H9HCNNNBKUMLXR_NEE } from "../imports/H9HCNNNBKUMLXR_NEE"
import { RK809_5 } from "../imports/RK809_5"
import { SYR837PKC } from "../imports/SYR837PKC"
import { SY8113BADC } from "../imports/SY8113BADC"
import { THGBMUG6C1LBAIL } from "../imports/THGBMUG6C1LBAIL"
import { XL2EL89COI_111YLC_24M } from "../imports/XL2EL89COI_111YLC_24M"
import { Q13FC13500004 } from "../imports/Q13FC13500004"
import { BSS138DW_7_F } from "../imports/BSS138DW_7_F"
import { HCB1005KF_121T20 } from "../imports/HCB1005KF_121T20"
import { WIP252012P_R47ML } from "../imports/WIP252012P_R47ML"
import { TFM252012ALMAR22MTAA } from "../imports/TFM252012ALMAR22MTAA"
import { XRIM404020S2R2MGCA } from "../imports/XRIM404020S2R2MGCA"
import roles from "./design/roles.json"

const IMPORTS: Record<string, any> = {
  RK3566, H9HCNNNBKUMLXR_NEE, RK809_5, SYR837PKC, SY8113BADC, THGBMUG6C1LBAIL, XL2EL89COI_111YLC_24M,
  Q13FC13500004, BSS138DW_7_F, HCB1005KF_121T20, WIP252012P_R47ML, TFM252012ALMAR22MTAA, XRIM404020S2R2MGCA,
}

/** Hirose DF40C-100DP-0.4V(51) header in the CM4 pin numbering: odd pins on one row, even on the other,
 *  pin n at 0.4 mm * floor((n-1)/2) along the connector, rows 2.71 mm apart, four hold-down pads at the ends.
 *  Local frame: length along +y from pin 1, odd row at -x when oddSide = -1. Pads are named "1".."100". */
export function cm4HeaderFootprint(oddSide: 1 | -1) {
  const pads: any[] = []
  for (let n = 1; n <= 100; n++) {
    const k = (n - 1) >> 1, y = -9.8 + 0.4 * k, x = (n % 2 ? oddSide : -oddSide) * 1.355
    pads.push(<smtpad key={n} portHints={[String(n)]} pcbX={`${x}mm`} pcbY={`${y}mm`} width="0.66mm" height="0.2mm" shape="rect" />)
  }
  for (const [i, [x, y]] of [[-1.355, -10.265], [1.355, -10.265], [-1.355, 10.265], [1.355, 10.265]].entries())
    pads.push(<smtpad key={"m" + i} portHints={["MH" + (i + 1)]} pcbX={`${x}mm`} pcbY={`${y}mm`} width="0.66mm" height="0.3mm" shape="rect" />)
  return <footprint>{pads}<courtyardoutline outline={[{ x: -1.93, y: -11.01 }, { x: 1.93, y: -11.01 }, { x: 1.93, y: 11.01 }, { x: -1.93, y: 11.01 }, { x: -1.93, y: -11.01 }]} /></footprint>
}

/** SYR837 WLCSP-20, 0.4 mm pitch, the same pads as the imported footprint (pin n in column (n-1)/4, row (n-1)%4)
 *  with an IPC courtyard: body 2.0 x 1.6 mm + 0.25 mm (the imported one is 5.2 x 4.9 mm). */
export function wlcsp20Footprint() {
  const pads: any[] = []
  for (let n = 1; n <= 20; n++) {
    const x = -0.8 + 0.4 * Math.floor((n - 1) / 4), y = -0.6 + 0.4 * ((n - 1) % 4)
    pads.push(<smtpad key={n} portHints={[`pin${n}`]} pcbX={`${x}mm`} pcbY={`${y}mm`} radius="0.104mm" shape="circle" />)
  }
  return <footprint>{pads}<courtyardoutline outline={[{ x: -1.25, y: -1.05 }, { x: 1.25, y: -1.05 }, { x: 1.25, y: 1.05 }, { x: -1.25, y: 1.05 }, { x: -1.25, y: -1.05 }]} /></footprint>
}

export function makePart(c: { ref: string; role: string; value: string }, place: any) {
  const r: any = (roles as any)[c.role]
  const common: any = { name: c.ref, schX: place.schX ?? 0, schY: place.schY ?? 0, pcbX: place.x, pcbY: place.y, pcbRotation: place.rot ?? 0, layer: place.layer ?? "top", supplierPartNumbers: { jlcpcb: [r.lcsc] } }
  if (c.role === "DF40_HEADER")
    return <chip key={c.ref} {...common} manufacturerPartNumber="DF40C-100DP-0.4V(51)" footprint={cm4HeaderFootprint(place.oddSide ?? -1)} pinLabels={Object.fromEntries(Array.from({ length: 100 }, (_, i) => [`pin${i + 1}`, [String(i + 1)]]))} />
  if (r.import) {
    const C = IMPORTS[r.import]
    const extra: any = c.role === "XTAL_24M" ? { loadCapacitance: "12pF" } : c.role === "XTAL_32K" ? { loadCapacitance: "12.5pF" } : c.role === "BUCK_CPU" ? { footprint: wlcsp20Footprint() } : {}
    return <C key={c.ref} {...common} {...extra} />
  }
  if (r.kind === "C") return <capacitor key={c.ref} {...common} capacitance={c.value} footprint={r.fp} />
  return <resistor key={c.ref} {...common} resistance={c.value} footprint={r.fp} />
}
