// Renders the RK3566 + LPDDR4 module board as it stands: tscircuit renders the board and the two BGAs; the routed and
// verified DDR block (source/route/ddr.lane.routed.json) and the power-ball fanout (source/route/power.fanout.json)
// are then added to the circuit JSON as plain PCB traces and vias. Output: index.circuit.json
import { Circuit } from "@tscircuit/core"
import { RK3566 } from "../imports/RK3566"
import { H9HCNNNBKUMLXR_NEE } from "../imports/H9HCNNNBKUMLXR_NEE"
const dir = import.meta.dir
const ddr = await Bun.file(dir + "/route/ddr.lane.routed.json").json()
const power: any[] = await Bun.file(dir + "/route/power.fanout.json").json()
const meta = await Bun.file(dir + "/route/power.meta.json").json()
const input = await Bun.file(dir + "/route/ddr.input.json").json()
const railOf: Record<string, string> = Object.fromEntries(meta.powerConnections.map((c: any) => [c.name, c.netConnectionName]))
// placement the routing was done with (fitted to every one of the 765 pads)
const U1 = { x: 0, y: 0 }, U2 = { x: -4, y: 16.6 }
// board outline: the copper and both packages with a 1.5 mm margin (provisional; the module outline is not designed yet)
const xs: number[] = [], ys: number[] = []
for (const o of input.obstacles) { xs.push(o.center.x - o.width / 2, o.center.x + o.width / 2); ys.push(o.center.y - o.height / 2, o.center.y + o.height / 2) }
for (const t of [...ddr.traces, ...power]) for (const p of t.route) { xs.push(p.x); ys.push(p.y) }
const M = 1.5, x0 = Math.min(...xs) - M, x1 = Math.max(...xs) + M, y0 = Math.min(...ys) - M, y1 = Math.max(...ys) + M
const CX = (x0 + x1) / 2, CY = (y0 + y1) / 2
const circuit = new Circuit()
circuit.add(
  <board width={+(x1 - x0).toFixed(2)} height={+(y1 - y0).toFixed(2)} layers={6} thickness={1.6} routingDisabled schAutoLayoutEnabled={false}
    minTraceWidth={0.1} minTraceToPadEdgeClearance={0.1} minViaHoleDiameter={0.15} minViaPadDiameter={0.25} isViaInPadAllowed={true}
    title="RK3566 + LPDDR4 module (DDR block routed)">
    <RK3566 name="U1" pcbX={U1.x - CX} pcbY={U1.y - CY} />
    <H9HCNNNBKUMLXR_NEE name="U2" pcbX={U2.x - CX} pcbY={U2.y - CY} />
  </board>,
)
await circuit.renderUntilSettled()
// the module's netlist is not written yet, so every ball still reads as floating: drop those placeholder errors
const cj: any[] = circuit.getCircuitJson().filter((e: any) => e.type !== "source_pin_must_be_connected_error")
const ALL = ["top", "inner1", "inner2", "inner3", "inner4", "bottom"]
let n = 0
const via = (p: any, net: string) => cj.push({ type: "pcb_via", pcb_via_id: `r_via_${n++}`, x: p.x - CX, y: p.y - CY, hole_diameter: p.via_hole_diameter ?? 0.15, outer_diameter: p.via_diameter ?? 0.25, layers: ALL, from_layer: "top", to_layer: "bottom", net_name: net })
const trace = (pts: any[], layer: string, net: string) => cj.push({ type: "pcb_trace", pcb_trace_id: `r_trace_${n++}`, net_name: net, route: pts.map((p) => ({ route_type: "wire", x: p.x - CX, y: p.y - CY, width: p.width ?? 0.11, layer })) })
const add = (t: any, net: string) => {
  let cur: any[] = [], layer = t.route[0].layer
  const flush = () => { if (cur.length > 1) trace(cur, layer, net); cur = [] }
  for (const p of t.route) {
    if (p.route_type === "via") { flush(); via(p, net); layer = p.to_layer; cur = []; continue }
    if (p.layer !== layer) { flush(); layer = p.layer }
    cur.push(p)
  }
  flush()
}
for (const t of ddr.traces) add(t, t.connection_name)
for (const t of power) add(t, railOf[t.connection_name] ?? t.connection_name)
await Bun.write(dir + "/../index.circuit.json", JSON.stringify(cj))
const count = (k: string) => cj.filter((e) => e.type === k).length
const errs = cj.filter((e) => e.type.includes("error"))
console.log(`board ${(x1 - x0).toFixed(2)} x ${(y1 - y0).toFixed(2)} mm; components ${count("pcb_component")}, pads ${count("pcb_smtpad")}, traces ${count("pcb_trace")}, vias ${count("pcb_via")}, errors ${errs.length}`)
for (const e of errs.slice(0, 5)) console.log("  ", e.type, (e.message ?? "").slice(0, 160))
