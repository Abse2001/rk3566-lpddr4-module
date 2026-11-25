// Power/ground to the planes. A ball whose same-layer neighbours are at least viaD + w + 2*gap away takes
// its via in its own pad (filled via-in-pad, free at JLCPCB on 6+ layers) and leaves every channel between
// balls free; balls in a finer field (the RK3566 0.4 mm band) are fanned out with FanoutSolver to vias
// beside the field. env: OUT (output), PWR (plane layer for non-GND rails, default inner2)
import { FanoutSolver } from "/home/user/ts/fanout-solver/lib/index.ts"
const D = "/tmp/claude-0/-home-user/b9d79f2d-030e-532c-84b5-c3a79e3230d3/scratchpad/rk/"
const input = await Bun.file(D + "v3.input.json").json(), meta = await Bun.file(D + "v2.meta.json").json()
const VIA = 0.25, HOLE = 0.15, W = 0.11, GAP = 0.1, PITCH = VIA + W + 2 * GAP
const bb = (os: any[]) => ({ minX: Math.min(...os.map((o) => o.center.x - o.width / 2)), maxX: Math.max(...os.map((o) => o.center.x + o.width / 2)), minY: Math.min(...os.map((o) => o.center.y - o.height / 2)), maxY: Math.max(...os.map((o) => o.center.y + o.height / 2)) })
const { obstacles, connections, traces, buses, differentialPairs, ...rules } = input
const plane = (c: any) => (c.netConnectionName === "GND" ? "inner1" : (process.env.PWR ?? "inner2"))
const pads = obstacles.filter((o: any) => !o.isCopperPour && o.layers?.length === 1)
const roomy = (p: any) => {
  const o = pads.find((q: any) => Math.hypot(q.center.x - p.x, q.center.y - p.y) < 1e-3)
  if (!o || Math.min(o.width, o.height) < VIA - 1e-9) return false
  return pads.every((q: any) => q === o || q.layers[0] !== o.layers[0] || Math.hypot(q.center.x - p.x, q.center.y - p.y) >= PITCH - 1e-6)
}
// the DDR corridor between the two packages stays free of power copper: it is where the bus escapes
const b1 = bb(obstacles.filter((o: any) => o.componentId === "U1")), b2 = bb(obstacles.filter((o: any) => o.componentId === "U2"))
const lo = b1.maxY < b2.minY ? b1 : b2, hi = lo === b1 ? b2 : b1
// each half of the gap is kept clear across the span of that package's DDR balls (ball margin 0.3 mm)
const spanOf = (b: any) => { const xs = connections.flatMap((c: any) => c.pointsToConnect).filter((p: any) => p.y >= b.minY && p.y <= b.maxY && p.x >= b.minX && p.x <= b.maxX).map((p: any) => p.x); return [Math.min(...xs) - 0.3, Math.max(...xs) + 0.3] }
const mid = (lo.maxY + hi.minY) / 2, LAY = ["top", "inner1", "inner2", "inner3", "inner4", "bottom"]
const box = (id: string, [x0, x1]: number[], y0: number, y1: number) => ({ type: "rect", obstacleId: id, center: { x: (x0 + x1) / 2, y: (y0 + y1) / 2 }, width: x1 - x0, height: y1 - y0, layers: LAY, connectedTo: [] })
const corridor = [box("ddr-corridor-lo", spanOf(lo), lo.maxY + 0.05, mid), box("ddr-corridor-hi", spanOf(hi), mid, hi.minY - 0.05)]
// and outside every other package edge that DDR balls in the perimeter band escape across, a strip
// as deep as a pair breakout (EDGE_DEPTH) along the span of those balls
const EDGE_BAND = 1.0, EDGE_DEPTH = 1.5
for (const b of [b1, b2]) {
  const ps = connections.flatMap((c: any) => c.pointsToConnect).filter((p: any) => p.y >= b.minY && p.y <= b.maxY && p.x >= b.minX && p.x <= b.maxX)
  const near = (f: (p: any) => boolean) => ps.filter(f)
  const sides: [string, any[], (q: any[]) => any][] = [
    ["L", near((p) => p.x - b.minX < EDGE_BAND), (q) => box("ddr-edge-L", [b.minX - EDGE_DEPTH, b.minX - 0.05], Math.min(...q.map((p) => p.y)) - 0.3, Math.max(...q.map((p) => p.y)) + 0.3)],
    ["R", near((p) => b.maxX - p.x < EDGE_BAND), (q) => box("ddr-edge-R", [b.maxX + 0.05, b.maxX + EDGE_DEPTH], Math.min(...q.map((p) => p.y)) - 0.3, Math.max(...q.map((p) => p.y)) + 0.3)],
    ["B", near((p) => p.y - b.minY < EDGE_BAND), (q) => box("ddr-edge-B", [Math.min(...q.map((p) => p.x)) - 0.3, Math.max(...q.map((p) => p.x)) + 0.3], b.minY - EDGE_DEPTH, b.minY - 0.05)],
    ["T", near((p) => b.maxY - p.y < EDGE_BAND), (q) => box("ddr-edge-T", [Math.min(...q.map((p) => p.x)) - 0.3, Math.max(...q.map((p) => p.x)) + 0.3], b.maxY + 0.05, b.maxY + EDGE_DEPTH)],
  ]
  for (const [, q, mk] of sides) if (q.length >= 2) corridor.push(mk(q))
}
console.log("corridor", JSON.stringify(corridor.map((c) => [c.center, c.width, c.height])))
let fixed: any[] = []
for (const chip of ["U1", "U2"]) {
  const chipPads = obstacles.filter((o: any) => o.componentId === chip), cb = bb(chipPads)
  const power = meta.powerConnections.filter((c: any) => c.name.startsWith(`power_${chip}_`))
  const inPad = power.filter((c: any) => roomy(c.pointsToConnect[0]))
  for (const c of inPad) {
    const p = c.pointsToConnect[0]
    fixed.push({ type: "pcb_trace", pcb_trace_id: `vip:${c.name}`, connection_name: c.name, route: [
      { route_type: "wire", x: p.x, y: p.y, width: W, layer: "top" },
      { route_type: "via", x: p.x, y: p.y, from_layer: "top", to_layer: plane(c), via_diameter: VIA, via_hole_diameter: HOLE },
      { route_type: "wire", x: p.x, y: p.y, width: W, layer: plane(c) }] })
  }
  const rest = power.filter((c: any) => !inPad.includes(c))
  console.log(`${chip}: ${inPad.length} via-in-pad, ${rest.length} to fan out`)
  if (!rest.length) continue
  const srj = { ...rules, allowViaInPad: false, layerCount: 6, obstacles: [...obstacles, ...corridor], connections: rest, traces: fixed, buses: [], differentialPairs: [] }
  const options: any = { sourceComponentId: chip, componentBounds: { [chip]: cb }, sharedBoundary: { minX: cb.minX - 1, maxX: cb.maxX + 1, minY: cb.minY - 1, maxY: cb.maxY + 1 }, escapeLayers: ["top", "bottom"], maxLayerCombinations: 256, allowBlindAndBuriedVias: false, allowSameNetMerges: true, compactBusTracks: false,
    traceWidth: 0.1, clearance: 0.1, viaDiameter: VIA, viaHoleDiameter: HOLE,
    buses: rest.map((c: any) => ({ busId: c.name, connectionNames: [c.name], sourceComponentId: chip, direction: "down", termination: { type: "plane", layer: plane(c) } })) }
  const t0 = performance.now()
  const solver = new FanoutSolver(srj as any, options); solver.solve()
  if (!solver.solved) { console.log(`${chip}: POWER FANOUT FAILED: ${solver.error} ${JSON.stringify((solver as any).bestAttempt?.summary?.failedBusIds ?? (solver as any).bestAttempt?.failedBusIds)}`); process.exit(2) }
  const o = solver.getOutput()
  console.log(`${chip}: ${o.fanoutTraces.length}/${rest.length} fanned out in ${((performance.now() - t0) / 1e3).toFixed(1)}s, valid=${o.validation.valid}`)
  fixed = [...fixed, ...o.fanoutTraces]
}
await Bun.write(D + (process.env.OUT ?? "v5.power.json"), JSON.stringify(fixed))
const inp = await Bun.file(D + "v3.input.json").json(); inp.traces = fixed
await Bun.write(D + (process.env.OUT ?? "v5.power.json").replace("power", "withpower"), JSON.stringify(inp))
