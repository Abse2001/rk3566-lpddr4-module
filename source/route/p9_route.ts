// Experiment: route every non-DDR, non-plane net of the module with tscircuit's capacity-autorouter Pipeline 9
// (AutoroutingPipelineSolver9_PreloadedTraceGraph), instead of route.ts.
// Fixed copper: copper.json from the plane-drops run (DDR block, power fanout, BGA via-in-pad, plane drops).
// Signal layers: top / inner3 / bottom, mapped to SRJ layers top / inner1 / bottom (layerCount 3). inner2 (power
// islands) and inner1/inner4 (ground) are not offered to the router.
// Output: routes_p9.json (solver output traces) and copper_p9.json (fixed + routed, copper.json format).
import { AutoroutingPipelineSolver9_PreloadedTraceGraph } from "@tscircuit/capacity-autorouter"
const dir = import.meta.dir
const padsIn = await Bun.file(dir + "/../design/pads.json").json()
const base = await Bun.file(dir + "/" + (process.env.BASE ?? "copper.json")).json()
const W_SIG = 0.1, W_PWR = 0.2, W_BIG = 0.4, VIA_D = 0.25, VIA_H = 0.15
const PLANES = new Set(["GND", "VDD_CPU", "VDD_LOGIC", "VDD_GPU", "VDD_NPU", "VCC_DDR"])
const widthOf = (n: string) => (["VCC3V3_SYS", "VCC5V0_SYS"].includes(n) ? W_BIG : /^(VCC|VDD)/.test(n) ? W_PWR : W_SIG)
const WIDE = !!process.env.WIDE // default: route everything at 0.1 mm (power widths need neck-down, see report)
const toSrj: Record<string, string> = { top: "top", inner3: "inner1", bottom: "bottom" }
const fromSrj: Record<string, string> = { top: "top", inner1: "inner3", bottom: "bottom" }
const ALL = ["top", "inner1", "bottom"]
const B = padsIn.board

const obstacles: any[] = []
let oid = 0
for (const p of padsIn.pads) {
  const l = toSrj[p.layer]; if (!l) continue
  obstacles.push({ obstacleId: `pad${oid++}`, type: "rect", ...(p.shape === "circle" ? { shape: "circle" } : {}), layers: [l], center: { x: p.x, y: p.y }, width: p.w, height: p.h, connectedTo: p.net ? [p.net] : [], componentId: p.ref })
}
for (const v of base.vias) obstacles.push({ obstacleId: `via${oid++}`, type: "rect", shape: "circle", layers: ALL, center: { x: v.x, y: v.y }, width: v.d, height: v.d, connectedTo: v.net ? [v.net] : [] })
for (const v of padsIn.footprintVias) obstacles.push({ obstacleId: `fvia${oid++}`, type: "rect", shape: "circle", layers: ALL, center: { x: v.x, y: v.y }, width: v.d, height: v.d, connectedTo: ["GND"] })
// mounting holes: 2.7 mm hole, copper keeps 0.3 mm (obstacle grown so the obstacle margin adds the rest)
for (const [x, y] of [[0, 0], [33, 0], [0, -48], [33, -48]]) obstacles.push({ obstacleId: `hole${oid++}`, type: "rect", shape: "circle", isNonPlatedHole: true, layers: ALL, center: { x, y }, width: 2.7 + 0.4, height: 2.7 + 0.4, connectedTo: [] })

// fixed traces: preloaded, isFixed
const traces: any[] = []
let tid = 0
for (const t of base.traces) {
  const l = toSrj[t.layer]; if (!l) continue
  traces.push({ type: "pcb_trace", pcb_trace_id: `fixed_${tid++}`, isFixed: true, connection_name: t.net, route: t.pts.map((q: any) => ({ route_type: "wire", x: q.x, y: q.y, width: t.w, layer: l })) })
}

// connections: same terminals as route.ts (pads not covered by the net's fixed copper, plus the net's fixed vias)
const near = (p: any, x: number, y: number) => Math.abs(x - p.x) <= p.w / 2 + 0.01 && Math.abs(y - p.y) <= p.h / 2 + 0.01
const fixedTr = new Map<string, any[]>(), fixedV = new Map<string, any[]>()
for (const t of base.traces) (fixedTr.get(t.net) ?? fixedTr.set(t.net, []).get(t.net)!).push(t)
for (const v of base.vias) (fixedV.get(v.net) ?? fixedV.set(v.net, []).get(v.net)!).push(v)
const touches = (p: any) => (fixedTr.get(p.net) ?? []).some((t) => t.layer === p.layer && t.pts.some((q: any) => near(p, q.x, q.y))) || (fixedV.get(p.net) ?? []).some((v) => near(p, v.x, v.y))
const byNet = new Map<string, any[]>()
for (const p of padsIn.pads) if (p.net) (byNet.get(p.net) ?? byNet.set(p.net, []).get(p.net)!).push(p)
const connections: any[] = []
for (const [name, ps] of byNet) {
  if (PLANES.has(name)) continue
  if (process.env.SKIP && process.env.SKIP.split(",").includes(name)) continue
  if (name.startsWith("DDR_") && (fixedTr.has(name) || fixedV.has(name))) continue
  const open = ps.filter((p) => !touches(p))
  const pts: any[] = open.filter((p) => toSrj[p.layer]).map((p, k) => ({ x: p.x, y: p.y, layer: toSrj[p.layer], pointId: `${name}#${p.ref}.${p.names[0] ?? k}`, pcb_port_id: `${p.ref}.${p.names[0] ?? k}` }))
  const fv = fixedV.get(name) ?? []
  // fixed fanout vias of the net (fanout of the supply balls / power fanout) are reachable on every layer
  for (const v of fv) pts.push({ x: v.x, y: v.y, layers: ALL, pointId: `${name}#via${pts.length}` })
  if (!fv.length && ps.length !== open.length) { const p = ps.find((q) => touches(q)); pts.push({ x: p.x, y: p.y, layer: toSrj[p.layer], pointId: `${name}#fixed` }) }
  if (pts.length < 2) continue
  connections.push({ name, pointsToConnect: pts, nominalTraceWidth: WIDE ? widthOf(name) : W_SIG })
}
const differentialPairs: any[] = []
const names = new Set(connections.map((c) => c.name))
for (const n of names) {
  const m = /^(.*?)(P|_P|DP)(_C)?$/.exec(n); if (!m) continue
  const neg = m[1] + ({ P: "N", _P: "_N", DP: "DM" } as any)[m[2]] + (m[3] ?? "")
  if (names.has(neg)) differentialPairs.push({ connectionNames: [n, neg], lengthTolerance: /^USB/.test(n) ? 0.25 : 0.13 })
}
const M = +(process.env.MARGIN ?? 0.1)
const srj: any = {
  layerCount: 3, minTraceWidth: W_SIG, nominalTraceWidth: W_SIG, minViaHoleDiameter: VIA_H, minViaPadDiameter: VIA_D,
  defaultObstacleMargin: M, minTraceToPadEdgeClearance: M, minBoardEdgeClearance: 0.3, minViaEdgeToPadEdgeClearance: M,
  minViaHoleEdgeToViaHoleEdgeClearance: 0.2, minPadEdgeToPadEdgeClearance: M, allowViaInPad: true,
  obstacles, connections, differentialPairs, traces,
  bounds: { minX: B.x0, maxX: B.x1, minY: B.y0, maxY: B.y1 },
}
await Bun.write(dir + "/p9.input.json", JSON.stringify(srj))
console.log(`SRJ: ${obstacles.length} obstacles, ${connections.length} connections, ${differentialPairs.length} pairs, ${traces.length} fixed traces`)
if (process.env.INPUT_ONLY) process.exit(0)

const t0 = performance.now()
const solver = new AutoroutingPipelineSolver9_PreloadedTraceGraph(srj, { effort: +(process.env.EFFORT ?? 1) })
let last = 0, lastPhase = ""
const MAXSEC = +(process.env.MAXSEC ?? 3000)
while (!solver.solved && !solver.failed) {
  solver.step()
  const s = (performance.now() - t0) / 1e3
  const phase = (solver as any).getCurrentPhase?.() ?? (solver as any).activeSubSolver?.getSolverName?.() ?? ""
  if (phase !== lastPhase || s - last > 30) { console.log(`[${s.toFixed(0)}s] ${phase} it=${solver.iterations}`); last = s; lastPhase = phase }
  if (s > MAXSEC) { console.log("time limit"); break }
}
console.log(solver.solved ? "SOLVED" : solver.failed ? `FAILED: ${solver.error}` : "STOPPED", `${((performance.now() - t0) / 1e3).toFixed(0)}s`)
let out: any[] = []
try { out = solver.getOutputSimplifiedPcbTraces() } catch (e) { console.log("no output:", String(e).slice(0, 300)) }
const routed = out.filter((t: any) => !String(t.pcb_trace_id).startsWith("fixed_") && !t.isFixed)
const segs: any[] = [], vias: any[] = []
for (const t of routed) {
  const net = t.connection_name?.replace(/_mst\d+$|__.*$/, "") ?? "?"
  let run: any[] = [], layer = "", w = W_SIG
  const flush = () => { if (run.length >= 2) segs.push({ net, layer: fromSrj[layer] ?? layer, w, pts: run }); run = [] }
  for (const r of t.route) {
    if (r.route_type === "wire") { if (r.layer !== layer) { flush(); layer = r.layer; w = r.width } run.push({ x: r.x, y: r.y }) }
    else if (r.route_type === "via") { flush(); vias.push({ x: r.x, y: r.y, d: r.via_diameter ?? VIA_D, hole: r.via_hole_diameter ?? VIA_H, net }); layer = "" }
  }
  flush()
}
await Bun.write(dir + "/routes_p9.json", JSON.stringify({ solved: solver.solved, error: solver.failed ? String(solver.error) : null, traces: routed }))
await Bun.write(dir + "/copper_p9.json", JSON.stringify({ traces: [...base.traces, ...segs], vias: [...base.vias, ...vias] }))
console.log(`routed traces ${routed.length}, segments ${segs.length}, vias ${vias.length}`)
