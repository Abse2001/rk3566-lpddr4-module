// Renders the module: the board, every part at its placement (design/placement.json) with its nets
// (design/netlist.json), then adds the copper made outside tscircuit as plain PCB elements: the routed DDR
// block, the power-ball fanout, the routed signals (route/routes.json) and the planes (route/planes.json).
// MODE=pads writes design/pads.json (every pad with its net) for the router instead of the full board.
import { Circuit } from "@tscircuit/core"
import { makePart } from "./parts"
import netlist from "./design/netlist.json"
import placement from "./design/placement.json"
const dir = import.meta.dir
const RK = { x: 15.2, y: -19.0 }
const BOARD = { x0: -3.5, x1: 36.5, y0: -51.5, y1: 3.5 }
const CX = (BOARD.x0 + BOARD.x1) / 2, CY = (BOARD.y0 + BOARD.y1) / 2
const comps = netlist.components as any[]
const place = placement as any
const circuit = new Circuit()
circuit.add(
  <board width={BOARD.x1 - BOARD.x0} height={BOARD.y1 - BOARD.y0} layers={6} thickness={1.6} routingDisabled schAutoLayoutEnabled={false}
    minTraceWidth={0.1} minTraceToPadEdgeClearance={0.1} minViaHoleDiameter={0.15} minViaPadDiameter={0.25} isViaInPadAllowed={true}
    title="RK3566 + LPDDR4 compute module (CM4 form factor)">
    <group pcbX={-CX} pcbY={-CY}>
      {comps.map((c) => makePart(c, place[c.ref]))}
      {[[0, 0], [33, 0], [0, -48], [33, -48]].map(([x, y], i) => <hole key={i} name={"H" + (i + 1)} pcbX={x} pcbY={y} diameter={2.7} />)}
    </group>
  </board>,
)
await circuit.renderUntilSettled()
const raw: any[] = circuit.getCircuitJson()
// the netlist lives in design/netlist.json; tscircuit sees no traces, so its "floating pin" notices are dropped
const cj: any[] = raw.filter((e) => e.type !== "source_pin_must_be_connected_error")
// ---------- pads with their nets ----------
const srcName = Object.fromEntries(cj.filter((e) => e.type === "source_component").map((e) => [e.source_component_id, e.name]))
const pcbComp = Object.fromEntries(cj.filter((e) => e.type === "pcb_component").map((e) => [e.pcb_component_id, srcName[e.source_component_id]]))
const sport = Object.fromEntries(cj.filter((e) => e.type === "source_port").map((e) => [e.source_port_id, e]))
const pport = Object.fromEntries(cj.filter((e) => e.type === "pcb_port").map((e) => [e.pcb_port_id, e]))
const byRef = Object.fromEntries(comps.map((c) => [c.ref, c]))
// a netlist pin name matches a port by name/hint, or covers numbered ports ("VCC" -> VCC1..VCC4, "GND" -> GND1..)
function netOf(ref: string, names: string[]): string | null {
  const c = byRef[ref]
  if (!c) return null
  for (const n of names) if (n in c.pins) return c.pins[n]
  for (const n of names) {
    const base = n.replace(/\d+$/, "")
    if (base !== n && base in c.pins && !/^pin$/.test(base)) return c.pins[base]
  }
  for (const n of names) { const m = /^pin(\d+)$/.exec(n); if (m && m[1] in c.pins) return c.pins[m[1]] }
  return null
}
const pads: any[] = []
for (const p of cj.filter((e) => e.type === "pcb_smtpad")) {
  const ref = pcbComp[p.pcb_component_id], sp = sport[pport[p.pcb_port_id]?.source_port_id]
  const names = [...new Set([sp?.name, ...(sp?.port_hints ?? [])].filter(Boolean))] as string[]
  // rotated pads carry their unrotated size: at 90/270 degrees width and height swap (only right angles are used)
  const rot = p.ccw_rotation ?? 0, quarter = Math.round(rot / 90) % 2 !== 0
  const w0 = p.width ?? p.radius * 2, h0 = p.height ?? p.radius * 2
  pads.push({ ref, names, net: netOf(ref, names), x: +(p.x + CX).toFixed(4), y: +(p.y + CY).toFixed(4), w: quarter ? h0 : w0, h: quarter ? w0 : h0, shape: p.shape === "circle" ? "circle" : "rect", layer: p.layer, rot })
}
const vias = cj.filter((e) => e.type === "pcb_via").map((v) => ({ x: v.x + CX, y: v.y + CY, d: v.outer_diameter, hole: v.hole_diameter, ref: pcbComp[v.pcb_component_id] }))
if (process.env.MODE === "pads") {
  await Bun.write(dir + "/design/pads.json", JSON.stringify({ pads, footprintVias: vias, board: BOARD, rk: RK }))
  const unnamed = pads.filter((p) => p.net === null && !["U1", "U2", "U6"].includes(p.ref) && !/^NC/.test(p.names[0] ?? ""))
  console.log(`pads ${pads.length}, footprint vias ${vias.length}; pads without a net: ${unnamed.length}`, unnamed.slice(0, 12).map((p) => `${p.ref}.${p.names[0]}`).join(" "))
  const errs = cj.filter((e) => e.type.includes("error")); console.log("errors", errs.length, errs.slice(0, 3).map((e) => e.message?.slice(0, 120)))
  process.exit(0)
}
// ---------- copper made outside tscircuit ----------
const ALL = ["top", "inner1", "inner2", "inner3", "inner4", "bottom"]
let n = 0
const via = (x: number, y: number, d: number, hole: number, net: string) => cj.push({ type: "pcb_via", pcb_via_id: `r_via_${n++}`, x: x - CX, y: y - CY, hole_diameter: hole, outer_diameter: d, layers: ALL, from_layer: "top", to_layer: "bottom", net_name: net })
const trace = (pts: any[], layer: string, w: number, net: string) => cj.push({ type: "pcb_trace", pcb_trace_id: `r_trace_${n++}`, net_name: net, route: pts.map((p) => ({ route_type: "wire", x: p.x - CX, y: p.y - CY, width: w, layer })) })
const copper = await Bun.file(process.env.COPPER ?? dir + "/route/copper.json").json()
for (const t of copper.traces) trace(t.pts, t.layer, t.w, t.net)
for (const v of copper.vias) via(v.x, v.y, v.d, v.hole, v.net)
const PL = process.env.PLANES ?? dir + "/route/planes.json"
const planes = (await Bun.file(PL).exists()) ? await Bun.file(PL).json() : []
for (const p of [...planes].sort((a: any, b: any) => b.area - a.area))
  cj.push({ type: "pcb_copper_pour", pcb_copper_pour_id: `r_pour_${n++}`, shape: "brep", layer: p.layer, net_name: p.net, covered_with_solder_mask: true,
    brep_shape: { outer_ring: { vertices: p.outer.map((q: any) => ({ x: q.x - CX, y: q.y - CY })) }, inner_rings: p.holes.map((h: any[]) => ({ vertices: h.map((q) => ({ x: q.x - CX, y: q.y - CY })) })) } })
// ---------- connectivity: the nets of design/netlist.json as circuit-json nets ----------
// one source_net + one source_trace per net (listing every source_port on it); every port, routed trace, via and
// copper pour points to its net, so the viewer highlights a net as one piece and `tsci check shorts` knows which
// copper belongs together. The routed copper carries its net in route/copper.json (`net` below).
const portNet: Record<string, string> = {}
for (const sp of cj.filter((e) => e.type === "source_port")) {
  const ref = srcName[sp.source_component_id], names = [...new Set([sp.name, ...(sp.port_hints ?? [])].filter(Boolean))] as string[]
  const nn = ref ? netOf(ref, names) : null
  if (nn) portNet[sp.source_port_id] = nn
}
const subId = cj.find((e) => e.type === "source_port" && e.subcircuit_id)?.subcircuit_id
const netIds: Record<string, { net: string; trace: string; key: string }> = {}
const netNames = [...new Set([...Object.values(portNet), ...copper.traces.map((t: any) => t.net), ...copper.vias.map((v: any) => v.net), ...planes.map((p: any) => p.net)].filter(Boolean))] as string[]
netNames.forEach((name, i) => {
  const ids = { net: `source_net_${i}`, trace: `source_trace_net_${i}`, key: `net_${name}` }; netIds[name] = ids
  cj.push({ type: "source_net", source_net_id: ids.net, name, member_source_group_ids: [], subcircuit_id: subId, subcircuit_connectivity_map_key: ids.key,
    is_ground: name === "GND", is_power: /^(VCC|VDD)/.test(name) })
  cj.push({ type: "source_trace", source_trace_id: ids.trace, connected_source_port_ids: Object.keys(portNet).filter((k) => portNet[k] === name),
    connected_source_net_ids: [ids.net], subcircuit_id: subId, subcircuit_connectivity_map_key: ids.key, display_name: name })
})
for (const e of cj) {
  if (e.type === "source_port" && portNet[e.source_port_id]) e.subcircuit_connectivity_map_key = netIds[portNet[e.source_port_id]].key
  if (e.type === "pcb_trace" && e.net_name && netIds[e.net_name]) { e.source_trace_id = netIds[e.net_name].trace; delete e.net_name }
  if (e.type === "pcb_via") {
    // routed vias carry net_name; part footprint vias (thermal-pad vias) are ground
    const nm = e.net_name ?? (e.pcb_component_id || e.pcb_port_ids ? "GND" : null)
    if (nm && netIds[nm]) { e.source_trace_id = netIds[nm].trace; e.source_net_id = netIds[nm].net; e.subcircuit_connectivity_map_key = netIds[nm].key }
    delete e.net_name
  }
  if (e.type === "pcb_copper_pour" && e.net_name && netIds[e.net_name]) { e.source_net_id = netIds[e.net_name].net; delete e.net_name }
}
// tscircuit flagged every pin as unrouted because it saw no traces; the nets above connect them
for (let i = cj.length - 1; i >= 0; i--) if (cj[i].type === "source_pin_missing_trace_warning") cj.splice(i, 1)
// JLCPCB silkscreen minimums: line width 0.15 mm, text 1.0 mm high. Reference designators at a legible 1 mm do not
// fit on this board, so silk text smaller than that is dropped (assembly is placed from the CPL; the designators stay
// on the fab layer), and silk lines are drawn at least 0.15 mm wide
for (let i = cj.length - 1; i >= 0; i--) if (cj[i].type === "pcb_silkscreen_text" && (cj[i].font_size ?? 0) < 1.0) cj.splice(i, 1)
for (const e of cj) if (e.type === "pcb_silkscreen_path" && (e.stroke_width ?? 0) < 0.15) e.stroke_width = 0.15
// drop interior points of straight runs (same layer and width): the geometry is unchanged, the file much smaller
for (const e of cj) if (e.type === "pcb_trace") e.route = e.route.filter((b: any, k: number, r: any[]) => {
  const a = r[k - 1], c = r[k + 1]
  if (!a || !c || [a, b, c].some((q) => q.route_type !== "wire") || a.layer !== b.layer || b.layer !== c.layer || a.width !== b.width || b.width !== c.width) return true
  return Math.abs((b.x - a.x) * (c.y - b.y) - (b.y - a.y) * (c.x - b.x)) > 1e-9 || (b.x - a.x) * (c.x - b.x) + (b.y - a.y) * (c.y - b.y) < 0
})
// coordinates rounded to 0.1 um: keeps the file under the tscircuit.com upload limit
await Bun.write(process.env.CIRCUIT ?? dir + "/../index.circuit.json", JSON.stringify(cj, (_k, v) => (typeof v === "number" && !Number.isInteger(v) ? Math.round(v * 1e4) / 1e4 : v)))
const count = (k: string) => cj.filter((e) => e.type === k).length
console.log(`components ${count("pcb_component")}, pads ${count("pcb_smtpad")}, traces ${count("pcb_trace")}, vias ${count("pcb_via")}, pours ${count("pcb_copper_pour")}`)
