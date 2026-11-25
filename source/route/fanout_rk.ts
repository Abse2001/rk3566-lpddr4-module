// Escapes the RK3566's (U1) non-DDR signal balls with @tscircuit/fanout-solver: every ball reaches the edge of a
// shared boundary around the ball field on top / inner3 / bottom, around the fixed DDR copper, the supplied power
// fanout and the via-in-pad of the supply balls. Output: route/rk_escape.json (escape copper + endpoints per net).
// Experimental; the live pipeline (route.ts) is unchanged.
//   env: FANOUT=/path/to/fanout-solver (default /home/user/fanout-solver), GROUP=edge|ring, OUT=file
import { FanoutSolver, validateRoutedCopperDrc } from "/home/user/fanout-solver/lib/index.ts"
const dir = import.meta.dir
const padsIn = await Bun.file(dir + "/../design/pads.json").json()
const fixed = await Bun.file(dir + "/fixed.json").json()
const bga = await Bun.file(dir + "/bga_vias.json").json()
const pads: any[] = padsIn.pads
const W = 0.1, CLR = 0.1, VIA_D = 0.25, VIA_H = 0.15
const LAYERS6 = ["top", "inner1", "inner2", "inner3", "inner4", "bottom"]
const SIG = ["top", "inner3", "bottom"]

// ---------- nets to escape ----------
const fixedNets = new Set<string>([...fixed.traces.map((t: any) => t.net), ...fixed.vias.map((v: any) => v.net), ...bga.map((v: any) => v.net)])
const byNet = new Map<string, any[]>()
for (const p of pads) if (p.net) (byNet.get(p.net) ?? byNet.set(p.net, []).get(p.net)!).push(p)
const u1 = pads.filter((p) => p.ref === "U1")
const field = { minX: Math.min(...u1.map((p) => p.x)), maxX: Math.max(...u1.map((p) => p.x)), minY: Math.min(...u1.map((p) => p.y)), maxY: Math.max(...u1.map((p) => p.y)) }
const M = +(process.env.MARGIN ?? 0.6)
const boundary = { minX: field.minX - M, maxX: field.maxX + M, minY: field.minY - M, maxY: field.maxY + M }
const nets: { name: string; ball: any; dest: any }[] = []
for (const [name, ps] of byNet) {
  if (name === "GND" || name.startsWith("DDR") || fixedNets.has(name)) continue
  const balls = ps.filter((p) => p.ref === "U1"), others = ps.filter((p) => p.ref !== "U1")
  if (balls.length !== 1 || !others.length) continue
  if (process.env.ONLY && !process.env.ONLY.split(",").includes(name)) continue
  const b = balls[0]
  const dest = others.reduce((a, q) => (Math.hypot(q.x - b.x, q.y - b.y) < Math.hypot(a.x - b.x, a.y - b.y) ? q : a))
  nets.push({ name, ball: b, dest })
}
// exit edge: where the destination lies relative to the field
const edgeOf = (d: any): "left" | "right" | "top" | "bottom" => {
  const dx = d.x < field.minX ? field.minX - d.x : d.x > field.maxX ? d.x - field.maxX : 0
  const dy = d.y < field.minY ? field.minY - d.y : d.y > field.maxY ? d.y - field.maxY : 0
  if (dx === 0 && dy === 0) {
    const m = [d.x - field.minX, field.maxX - d.x, d.y - field.minY, field.maxY - d.y]
    return (["left", "right", "bottom", "top"] as const)[m.indexOf(Math.min(...m))]
  }
  if (dx >= dy) return d.x < field.minX ? "left" : "right"
  return d.y < field.minY ? "bottom" : "top"
}
const OVERRIDE: Record<string, "left" | "right" | "top" | "bottom"> = {}
for (const [k, v] of Object.entries(JSON.parse(process.env.EDGES ?? "{}"))) OVERRIDE[k] = v as any
// differential pairs
const pairOf = (n: string) => {
  const m = /^(.*?)(P|_P|DP)(_C)?$/.exec(n)
  if (!m) return null
  const neg = m[1] + ({ P: "N", _P: "_N", DP: "DM" } as any)[m[2]] + (m[3] ?? "")
  return nets.some((q) => q.name === neg) ? neg : null
}
const pairs: [string, string][] = []
for (const n of nets) { const q = pairOf(n.name); if (q) pairs.push([n.name, q]) }
const partner = new Map<string, string>(); for (const [a, b] of pairs) { partner.set(a, b); partner.set(b, a) }
const edge = new Map<string, string>()
for (const n of nets) edge.set(n.name, OVERRIDE[n.name] ?? edgeOf(n.dest))
for (const [a, b] of pairs) edge.set(b, edge.get(a)!)
// buses: per edge, split by how deep the ball sits from that edge (rows of 0.65 mm), pairs kept together
const depth = (n: any) => {
  const e = edge.get(n.name)!, b = n.ball
  const d = e === "left" ? b.x - field.minX : e === "right" ? field.maxX - b.x : e === "bottom" ? b.y - field.minY : field.maxY - b.y
  return Math.round(d / 0.65)
}
const GROUP = process.env.GROUP ?? "ring"
const busMap = new Map<string, string[]>()
for (const n of nets) {
  const p = partner.get(n.name)
  const owner = p && p < n.name ? nets.find((q) => q.name === p)! : n
  const key = GROUP === "single" ? owner.name : GROUP === "edge" ? edge.get(n.name)! : `${edge.get(n.name)}_d${Math.min(depth(owner), 6)}`
  ;(busMap.get(key) ?? busMap.set(key, []).get(key)!).push(n.name)
}

// ---------- SimpleRouteJson ----------
const obstacles: any[] = []
for (const p of pads) {
  if (p.x < boundary.minX - 3 || p.x > boundary.maxX + 3 || p.y < boundary.minY - 3 || p.y > boundary.maxY + 3) { if (!nets.some((n) => n.dest === p)) continue }
  const ob: any = { type: "rect", layers: [p.layer], center: { x: p.x, y: p.y }, width: p.w, height: p.h, componentId: p.ref, connectedTo: p.net ? [p.net, `${p.ref}.${p.names[0]}`] : [`${p.ref}.${p.names[0]}`] }
  if (p.shape === "circle") ob.shape = "circle"
  obstacles.push(ob)
}
const viaOb = (x: number, y: number, d: number, net: string) => ({ type: "rect", shape: "circle", layers: LAYERS6, center: { x, y }, width: d, height: d, connectedTo: [net], isCopperPour: false })
for (const v of [...fixed.vias, ...bga]) obstacles.push(viaOb(v.x, v.y, v.d, v.net))
for (const v of padsIn.footprintVias) obstacles.push(viaOb(v.x, v.y, v.d, "GND"))
for (const t of fixed.traces) for (let k = 0; k + 1 < t.pts.length; k++) {
  const a = t.pts[k], b = t.pts[k + 1], L = Math.hypot(b.x - a.x, b.y - a.y)
  if (L < 1e-6) continue
  obstacles.push({ type: "rect", layers: [t.layer], center: { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 }, width: L + t.w, height: t.w, ccwRotationDegrees: (Math.atan2(b.y - a.y, b.x - a.x) * 180) / Math.PI, connectedTo: [t.net] })
}
const edgePoint = (n: any) => {
  const e = edge.get(n.name)!, b = n.ball
  const p = e === "left" ? { x: boundary.minX, y: b.y } : e === "right" ? { x: boundary.maxX, y: b.y } : e === "bottom" ? { x: b.x, y: boundary.minY } : { x: b.x, y: boundary.maxY }
  return { ...p, layer: "top", pointId: `exit:${n.name}` }
}
const connections = nets.map((n) => ({
  name: n.name, source_trace_id: n.name, width: W, nominalTraceWidth: W,
  // downstream point: the ball projected straight onto its exit edge (TARGET=dest uses the real destination pad,
  // which the solver projects onto the boundary and may reach by leaving and re-entering it)
  pointsToConnect: [{ x: n.ball.x, y: n.ball.y, layer: "top", pointId: `U1.${n.ball.names[0]}` }, process.env.TARGET === "dest" ? { x: n.dest.x, y: n.dest.y, layer: n.dest.layer, pointId: `${n.dest.ref}.${n.dest.names[0]}` } : edgePoint(n)],
}))
const buses = [...busMap].map(([id, names]) => ({ busId: id, name: id, connectionNames: names }))
const B = padsIn.board
const srj: any = {
  bounds: { minX: B.x0, maxX: B.x1, minY: B.y0, maxY: B.y1 }, obstacles, connections, buses, traces: [],
  differentialPairs: pairs.map(([a, b]) => ({ connectionNames: [a, b], lengthTolerance: 0.13 })),
  layerCount: 6, allowBlindAndBuriedVias: false, minTraceWidth: W, nominalTraceWidth: W,
  minViaDiameter: VIA_D, minViaPadDiameter: VIA_D, minViaHoleDiameter: VIA_H, min_via_hole_diameter: VIA_H, min_via_pad_diameter: VIA_D,
  minTraceToPadEdgeClearance: CLR, minViaEdgeToPadEdgeClearance: CLR, minViaHoleEdgeToViaHoleEdgeClearance: 0.2,
  minPlatedHoleDrillEdgeToDrillEdgeClearance: 0.2, minPadEdgeToPadEdgeClearance: 0.15, minBoardEdgeClearance: 0.3,
}
const options: any = {
  buses: buses.map((b) => ({ ...b, sourceComponentId: "U1", preferredExit: b.busId.split("_d")[0].split("_")[0] in { left: 1, right: 1, top: 1, bottom: 1 } ? b.busId.split("_d")[0] : edge.get(b.connectionNames[0]), allowedLayers: SIG })),
  sourceComponentId: "U1", sharedBoundary: boundary, escapeLayers: SIG, allowBlindAndBuriedVias: false,
  traceWidth: W, viaDiameter: VIA_D, viaHoleDiameter: VIA_H, clearance: CLR, compactBusTracks: true, borderDistribution: "even",
}
for (const b of options.buses) b.preferredExit = edge.get(b.connectionNames[0])
console.log(`nets ${nets.length}, pairs ${pairs.length}, buses ${buses.length}`, Object.fromEntries(["left", "right", "top", "bottom"].map((e) => [e, nets.filter((n) => edge.get(n.name) === e).length])))
await Bun.write(dir + "/rk_escape.input.json", JSON.stringify({ simpleRouteJson: srj, solverOptions: options }))
const t0 = performance.now()
const solver = new FanoutSolver(srj, options)
solver.solve()
const secs = ((performance.now() - t0) / 1e3).toFixed(1)
const best = Math.max(0, ...solver.attempts.map((a: any) => a.routedConnectionCount))
console.log(`solved=${solver.solved} failed=${solver.failed} ${secs}s attempts=${solver.attempts.length} best routed=${best}/${nets.length}`, solver.error ?? "")
if (!solver.solved) {
  const last: any = solver.attempts.at(-1)
  console.log("attempt summary", JSON.stringify(solver.attempts.map((a: any) => ({ routed: a.routedConnectionCount, failed: a.failedBusIds ?? a.failedBuses ?? a.failureReason })).slice(-3)).slice(0, 1500))
  process.exit(1)
}
const out = solver.getOutput()
const drc = validateRoutedCopperDrc({ inputSrj: srj, routedSrj: { ...out.simpleRouteJson, traces: out.fanoutTraces }, clearance: CLR, allowBlindAndBuriedVias: false })
console.log("validation", JSON.stringify(out.validation).slice(0, 300), "drc", drc.valid, drc.issues?.length, JSON.stringify(drc.issues?.slice(0, 3)).slice(0, 400))
await Bun.write(process.env.OUT ?? dir + "/rk_escape.json", JSON.stringify({ boundary, fanoutTraces: out.fanoutTraces, connections: out.simpleRouteJson.connections, validation: out.validation, drc }))
