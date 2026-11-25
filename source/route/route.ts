// Routes every module net that is not already fixed copper (the LPDDR4 block, the power-ball fanout):
// negotiated congestion on a 0.05 mm grid over the whole board, signal layers top / inner3 / bottom, through vias.
//
// - Signal nets are trees: each remaining terminal is joined to the copper already placed for the net.
// - Plane nets (GND on inner1/inner4; the core rails and the 3.3 V / 5 V system rails on inner2) only need each
//   pad joined to a via: the planes (planes.ts) connect the vias.
// - Clearances are exact: a trace centre may not come within (gap + half width) of other copper, a via centre
//   within (gap + via radius); copper keeps 0.3 mm from the board edge and from the mounting holes.
// - Space shared by two nets is priced up round after round (present + history cost) until no two nets conflict.
// Output: route/routes.json (per net: traces and vias) and route/copper.json (fixed + routed copper for build.tsx).
const dir = import.meta.dir
const padsIn = await Bun.file(dir + "/../design/pads.json").json()
const netlist = await Bun.file(dir + "/../design/netlist.json").json()
const fixed = await Bun.file(dir + "/fixed.json").json()
// via-in-pad on the SoC/eMMC supply and ground balls (fanout_bga.py): fixed copper too
if (await Bun.file(dir + "/bga_vias.json").exists()) fixed.vias.push(...(await Bun.file(dir + "/bga_vias.json").json()))

// ---------------- rules ----------------
const P = 0.05, GAP = 0.1 + 0.012, W_SIG = 0.1, W_PWR = 0.2, W_BIG = 0.4, VIA_D = 0.25, VIA_H = 0.15, EDGE = 0.3, EPS = 0.004
// inner2 is the power plane layer; small supply rails may also run there as traces (the plane islands avoid them)
const LAYERS = ["top", "inner3", "bottom", "inner2"] as const, NL = 4
const B = padsIn.board, X0 = B.x0, Y0 = B.y0
const NX = Math.round((B.x1 - B.x0) / P) + 1, NY = Math.round((B.y1 - B.y0) / P) + 1, NN = NX * NY
const gx = (x: number) => Math.round((x - X0) / P), gy = (y: number) => Math.round((y - Y0) / P)
const wx = (i: number) => X0 + i * P, wy = (j: number) => Y0 + j * P
const HOLES = [[0, 0], [33, 0], [0, -48], [33, -48]], HOLE_R = 1.35
const PLANE_GND = new Set(["GND"])
const PLANE_PWR = new Set(["VDD_CPU", "VDD_LOGIC", "VDD_GPU", "VDD_NPU", "VCC_DDR"])
const isPlane = (n: string) => PLANE_GND.has(n) || PLANE_PWR.has(n)
const widthOf = (n: string) => (["VCC3V3_SYS", "VCC5V0_SYS"].includes(n) ? W_BIG : !isPlane(n) && /^(VCC|VDD)/.test(n) ? W_PWR : W_SIG)
const SEED = +(process.env.SEED ?? 1), MAXIT = +(process.env.MAXIT ?? 60), VERB = !!process.env.VERB
let rng = SEED * 2654435761 % 4294967296
const rand = () => ((rng = (rng * 1664525 + 1013904223) % 4294967296) / 4294967296)

// ---------------- shapes ----------------
type Shape = { kind: "rect" | "circle" | "seg"; x: number; y: number; w?: number; h?: number; r?: number; x2?: number; y2?: number }
function dist(s: Shape, px: number, py: number): number { // distance from a point to the shape's copper edge (<0 inside)
  if (s.kind === "circle") return Math.hypot(px - s.x, py - s.y) - s.r!
  if (s.kind === "rect") { const dx = Math.abs(px - s.x) - s.w! / 2, dy = Math.abs(py - s.y) - s.h! / 2; return dx > 0 || dy > 0 ? Math.hypot(Math.max(dx, 0), Math.max(dy, 0)) : Math.max(dx, dy) }
  const ax = s.x, ay = s.y, bx = s.x2!, by = s.y2!, vx = bx - ax, vy = by - ay, L = vx * vx + vy * vy
  const k = L ? Math.max(0, Math.min(1, ((px - ax) * vx + (py - ay) * vy) / L)) : 0
  return Math.hypot(px - ax - k * vx, py - ay - k * vy) - s.r!
}
function bbox(s: Shape): [number, number, number, number] {
  if (s.kind === "circle") return [s.x - s.r!, s.y - s.r!, s.x + s.r!, s.y + s.r!]
  if (s.kind === "rect") return [s.x - s.w! / 2, s.y - s.h! / 2, s.x + s.w! / 2, s.y + s.h! / 2]
  return [Math.min(s.x, s.x2!) - s.r!, Math.min(s.y, s.y2!) - s.r!, Math.max(s.x, s.x2!) + s.r!, Math.max(s.y, s.y2!) + s.r!]
}
function cellsWithin(s: Shape, reach: number): number[] {
  const [a, b, c, d] = bbox(s), out: number[] = []
  for (let j = Math.max(0, gy(b - reach) - 1); j <= Math.min(NY - 1, gy(d + reach) + 1); j++)
    for (let i = Math.max(0, gx(a - reach) - 1); i <= Math.min(NX - 1, gx(c + reach) + 1); i++)
      if (dist(s, wx(i), wy(j)) < reach - EPS) out.push(j * NX + i)
  return out
}

// ---------------- static copper ----------------
// Each object: net, layers (indices into LAYERS; through vias: all), shape. Its "trace" stamp marks cells where a
// trace centre of another net may not go, its "via" stamp cells where another net's via centre may not go.
type Obj = { net: string | null; layers: number[]; shape: Shape; t?: Int32Array; tw?: Int32Array; tb?: Int32Array; v?: Int32Array; pad?: any }
const objs: Obj[] = []
const L_OF: Record<string, number> = { top: 0, inner3: 1, bottom: 2, inner2: 3 }
for (const p of padsIn.pads) {
  const l = L_OF[p.layer]
  const shape: Shape = p.shape === "circle" ? { kind: "circle", x: p.x, y: p.y, r: p.w / 2 } : { kind: "rect", x: p.x, y: p.y, w: p.w, h: p.h }
  objs.push({ net: p.net, layers: [l], shape, pad: p })
}
for (const v of padsIn.footprintVias) objs.push({ net: "GND", layers: [0, 1, 2, 3], shape: { kind: "circle", x: v.x, y: v.y, r: v.d / 2 } })
for (const t of fixed.traces) {
  const l = L_OF[t.layer]
  if (l === undefined) continue // plane-layer stubs of the fanout
  for (let i = 1; i < t.pts.length; i++)
    objs.push({ net: t.net, layers: [l], shape: { kind: "seg", x: t.pts[i - 1].x, y: t.pts[i - 1].y, x2: t.pts[i].x, y2: t.pts[i].y, r: t.w / 2 } })
}
for (const v of fixed.vias) objs.push({ net: v.net, layers: [0, 1, 2, 3], shape: { kind: "circle", x: v.x, y: v.y, r: v.d / 2 } })

const blockT = [0, 1, 2, 3].map(() => new Uint16Array(NN)), blockTW = [0, 1, 2, 3].map(() => new Uint16Array(NN)), blockTB = [0, 1, 2, 3].map(() => new Uint16Array(NN)), blockV = new Uint16Array(NN)
const R_T = GAP + W_SIG / 2, R_TW = GAP + W_PWR / 2, R_TB = GAP + W_BIG / 2, R_V = GAP + VIA_D / 2
for (const o of objs) {
  o.t = Int32Array.from(cellsWithin(o.shape, R_T)); o.tw = Int32Array.from(cellsWithin(o.shape, R_TW)); o.tb = Int32Array.from(cellsWithin(o.shape, R_TB)); o.v = Int32Array.from(cellsWithin(o.shape, R_V))
  for (const l of o.layers) { for (const c of o.t) blockT[l][c]++; for (const c of o.tw) blockTW[l][c]++; for (const c of o.tb) blockTB[l][c]++ }
  for (const c of o.v) blockV[c]++
}
// board edge and mounting holes
for (let j = 0; j < NY; j++) for (let i = 0; i < NX; i++) {
  const x = wx(i), y = wy(j), c = j * NX + i
  const de = Math.min(x - B.x0, B.x1 - x, y - B.y0, B.y1 - y), dh = Math.min(...HOLES.map(([hx, hy]) => Math.hypot(x - hx, y - hy) - HOLE_R))
  const d = Math.min(de, dh)
  if (d < EDGE + W_SIG / 2) for (let l = 0; l < NL; l++) blockT[l][c] += 1000
  if (d < EDGE + W_PWR / 2) for (let l = 0; l < NL; l++) blockTW[l][c] += 1000
  if (d < EDGE + W_BIG / 2) for (let l = 0; l < NL; l++) blockTB[l][c] += 1000
  if (d < EDGE + VIA_D / 2) blockV[c] += 1000
}
// neck-down zones: inside a BGA ball field a power trace narrows to signal width
const neck = new Uint8Array(NN)
{
  const bgas = new Map<string, number[]>()
  for (const p of padsIn.pads) if (/^[UJQ]\d/.test(p.ref)) { const b = bgas.get(p.ref) ?? [1e9, 1e9, -1e9, -1e9]; bgas.set(p.ref, [Math.min(b[0], p.x), Math.min(b[1], p.y), Math.max(b[2], p.x), Math.max(b[3], p.y)]) }
  for (const [, b] of bgas) for (let j = gy(b[1] - 0.6); j <= gy(b[3] + 0.6); j++) for (let i = gx(b[0] - 0.6); i <= gx(b[2] + 0.6); i++) if (i >= 0 && j >= 0 && i < NX && j < NY) neck[j * NX + i] = 1
}
// inner2 belongs to the core-rail islands under the SoC and their feeds from the regulators: no traces there
// (except in the DDR corner, where the supplied fanout drops some small rails onto inner2)
{
  const inBox = (x: number, y: number, b: number[]) => x >= b[0] && x <= b[2] && y >= b[1] && y <= b[3]
  // SoC field; LOGIC/GPU/NPU feeds from the RK809 below; the VDD_CPU feed from the north-east corner (U4/L6) along
  // the band between the eMMC and the SoC
  const ISLANDS = [[8.5, -26.5, 23.5, -11.5], [7.5, -35.0, 23.5, -26.5], [20.0, -11.8, 31.5, -9.0], [31.0, -11.0, 36.5, -2.5]]
  const DDR_CORNER = [6.5, -20.0, 13.5, -10.5]
  for (let j = 0; j < NY; j++) for (let i = 0; i < NX; i++) {
    const x = wx(i), y = wy(j)
    if (ISLANDS.some((b, k) => inBox(x, y, b) && !(k === 1 && process.env.INNER2_OPEN)) && !inBox(x, y, DDR_CORNER)) { blockT[3][j * NX + i] += 1000; blockTW[3][j * NX + i] += 1000; blockTB[3][j * NX + i] += 1000 }
  }
}
// inner2 corridors of the supply islands (planes.py, from a plane-drops-only run): another net's via there would
// cut the island off from its regulator, so only the rail's own vias may go there (outside the BGA fields)
const corr = new Int16Array(NN).fill(-1), corrName: string[] = []
if (!process.env.PLANES_ONLY && (await Bun.file(dir + "/corridors.json").exists())) {
  const cs = await Bun.file(dir + "/corridors.json").json()
  for (const c of cs) {
    const id = corrName.length; corrName.push(c.net)
    for (const [x, y] of c.cells) { const i = gx(x), j = gy(y); if (i >= 0 && j >= 0 && i < NX && j < NY && !neck[j * NX + i] && corr[j * NX + i] < 0) corr[j * NX + i] = id }
  }
  console.log("corridors", cs.length, "cells", corr.reduce((s, v) => s + (v >= 0 ? 1 : 0), 0))
  // INNER2_OPEN: between the SoC and the RK809 the islands keep only their feed corridors (widened by KEEP on each
  // side, so every feed stays >= CORR + 2 KEEP wide); slow signals may use the rest of inner2 there
  if (process.env.INNER2_OPEN) {
    const KEEP = Math.round(+(process.env.KEEP ?? 0.3) / P), SOUTH = [7.5, -35.0, 23.5, -26.5]
    let n = 0
    for (let j = 0; j < NY; j++) for (let i = 0; i < NX; i++) {
      const x = wx(i), y = wy(j)
      if (x < SOUTH[0] || x > SOUTH[2] || y < SOUTH[1] || y > SOUTH[3]) continue
      let hit = false
      for (let dj = -KEEP; dj <= KEEP && !hit; dj++) for (let di = -KEEP; di <= KEEP; di++) { const ii = i + di, jj = j + dj; if (ii >= 0 && jj >= 0 && ii < NX && jj < NY && corr[jj * NX + ii] >= 0) { hit = true; break } }
      if (hit) { const c = j * NX + i; blockT[3][c] += 1000; blockTW[3][c] += 1000; blockTB[3][c] += 1000; n++ }
    }
    console.log("inner2 open south of the SoC; feed corridors kept:", n, "cells")
  }
}
const objsByNet = new Map<string, Obj[]>()
for (const o of objs) if (o.net) (objsByNet.get(o.net) ?? objsByNet.set(o.net, []).get(o.net)!).push(o)
function lift(net: string, s: 1 | -1) {
  for (const o of objsByNet.get(net) ?? []) {
    for (const l of o.layers) { for (const c of o.t!) blockT[l][c] += s; for (const c of o.tw!) blockTW[l][c] += s; for (const c of o.tb!) blockTB[l][c] += s }
    for (const c of o.v!) blockV[c] += s
  }
}

// ---------------- nets and terminals ----------------
// A terminal is a set of graph nodes (layer * NN + cell): a pad's cells on its layer, or a via's cell on all layers.
type Term = { nodes: Int32Array; x: number; y: number; label: string }
type Net = { name: string; w: number; plane: boolean; inner2?: boolean; partner?: Net; follows?: Net; terms: Term[]; drops: Term[]; path?: Int32Array[]; vias?: number[]; conflicts?: number; order: number }
const padTerm = (p: any): Term => {
  const l = L_OF[p.layer]
  const shape: Shape = p.shape === "circle" ? { kind: "circle", x: p.x, y: p.y, r: p.w / 2 } : { kind: "rect", x: p.x, y: p.y, w: p.w, h: p.h }
  let cells = cellsWithin(shape, 0)
  if (!cells.length) cells = [gy(p.y) * NX + gx(p.x)]
  return { nodes: Int32Array.from(cells.map((c) => l * NN + c)), x: p.x, y: p.y, label: `${p.ref}.${p.names[0]}` }
}
const viaTerm = (v: any): Term => { const c = gy(v.y) * NX + gx(v.x); return { nodes: Int32Array.from([0, 1, 2, 3].map((l) => l * NN + c)), x: v.x, y: v.y, label: "via" } }
// fixed copper of a net, as connected groups touching pads: a pad covered by the net's fixed copper is done already
const fixedNets = new Set<string>([...fixed.traces.map((t: any) => t.net), ...fixed.vias.map((v: any) => v.net)])
const padsByNet = new Map<string, any[]>()
for (const p of padsIn.pads) if (p.net) (padsByNet.get(p.net) ?? padsByNet.set(p.net, []).get(p.net)!).push(p)
const fixedViasByNet = new Map<string, any[]>()
for (const v of fixed.vias) (fixedViasByNet.get(v.net) ?? fixedViasByNet.set(v.net, []).get(v.net)!).push(v)
const fixedTracesByNet = new Map<string, any[]>()
for (const t of fixed.traces) (fixedTracesByNet.get(t.net) ?? fixedTracesByNet.set(t.net, []).get(t.net)!).push(t)
function padTouchesFixed(p: any): boolean {
  const near = (x: number, y: number) => Math.abs(x - p.x) <= p.w / 2 + 0.01 && Math.abs(y - p.y) <= p.h / 2 + 0.01
  for (const t of fixedTracesByNet.get(p.net) ?? []) if (t.layer === p.layer && t.pts.some((q: any) => near(q.x, q.y))) return true
  for (const v of fixedViasByNet.get(p.net) ?? []) if (near(v.x, v.y)) return true
  return false
}
const nets: Net[] = []
for (const [name, ps] of padsByNet) {
  if (name.startsWith("DDR_") && fixedNets.has(name)) continue // routed LPDDR4 block
  const open = ps.filter((p) => !padTouchesFixed(p))
  if (isPlane(name)) {
    if (open.length) nets.push({ name, w: W_SIG, plane: true, terms: [], drops: open.map(padTerm), order: rand() })
    continue
  }
  // a signal or small-rail net: its pads plus (if any) its fixed copper as one more terminal
  const terms = open.map(padTerm)
  const fv = fixedViasByNet.get(name) ?? []
  if (fv.length) for (const v of fv) terms.push(viaTerm(v))
  else if (ps.length !== open.length) { const p = ps.find((q) => padTouchesFixed(q)); terms.push(padTerm(p)) }
  // inner2 (L3) sits next to the L2 ground plane: supply traces and slow signals may use it where the supply
  // islands do not; high-speed nets (HDMI, MIPI, PCIe, USB, eMMC, SD) stay on top / inner3 / bottom
  const fast = /^(HDMI_TX_[CD]|MIPI_|PCIE20_|USB_OTG0_D|EMMC_|CM4_SD_)/.test(name)
  if (terms.length >= 2) nets.push({ name, w: widthOf(name), plane: false, inner2: !fast, terms, drops: [], order: rand() })
}
// differential pairs: the negative net follows the positive one at the pair spacing
{
  const byName = new Map(nets.map((n) => [n.name, n]))
  for (const n of nets) {
    const m = /^(.*?)(P|_P|DP)(_C)?$/.exec(n.name)
    if (!m) continue
    const neg = byName.get(m[1] + ({ P: "N", _P: "_N", DP: "DM" } as any)[m[2]] + (m[3] ?? ""))
    if (neg && !neg.plane && !n.plane) { n.partner = neg; neg.follows = n }
  }
}
// ---------------- occupancy (other nets' routed copper) ----------------
const occT = [0, 1, 2, 3].map(() => new Uint16Array(NN)), occV = new Uint16Array(NN)
const histT = [0, 1, 2, 3].map(() => new Float32Array(NN)), histV = new Float32Array(NN)
const disk = (r: number) => { const o: number[] = []; const k = Math.ceil(r / P); for (let dj = -k; dj <= k; dj++) for (let di = -k; di <= k; di++) if (Math.hypot(di, dj) * P < r - EPS) o.push(di, dj); return o }
const D_TT = disk(W_SIG + GAP + 0.0), D_TTW = disk(W_PWR / 2 + W_SIG / 2 + GAP), D_TTB = disk(W_BIG / 2 + W_SIG / 2 + GAP), D_BTV = disk(W_BIG / 2 + GAP + VIA_D / 2), D_TV = disk(W_SIG / 2 + GAP + VIA_D / 2), D_VV = disk(VIA_D + GAP)
const D_WTV = disk(W_PWR / 2 + GAP + VIA_D / 2)
const D_EXW = disk((W_PWR - W_SIG) / 2 + P / 2), D_EXB = disk((W_BIG - W_SIG) / 2 + P / 2)
function stampDisk(arr: Uint16Array, c: number, offs: number[], s: number) {
  const i = c % NX, j = (c / NX) | 0
  for (let k = 0; k < offs.length; k += 2) { const ii = i + offs[k], jj = j + offs[k + 1]; if (ii >= 0 && jj >= 0 && ii < NX && jj < NY) arr[jj * NX + ii] += s }
}
function stampNet(n: Net, s: 1 | -1) {
  if (!n.path) return
  const DT = n.w > W_PWR ? D_TTB : n.w > W_SIG ? D_TTW : D_TT, DTV = n.w > W_PWR ? D_BTV : n.w > W_SIG ? D_WTV : D_TV
  for (const p of n.path) for (let k = 0; k < p.length; k++) {
    const id = p[k], l = (id / NN) | 0, c = id - l * NN
    stampDisk(occT[l], c, DT, s); stampDisk(occV, c, DTV, s)
  }
  for (const c of n.vias!) { for (let l = 0; l < NL; l++) stampDisk(occT[l], c, D_TV, s); stampDisk(occV, c, D_VV, s) }
}
// ---------------- search ----------------
const gCost = new Float32Array(NL * NN), from = new Int32Array(NL * NN), seen = new Uint32Array(NL * NN)
let stamp = 1
const heapK: number[] = [], heapV: number[] = []
const push = (k: number, v: number) => { heapK.push(k); heapV.push(v); let i = heapK.length - 1; while (i > 0) { const p = (i - 1) >> 1; if (heapK[p] <= heapK[i]) break;[heapK[p], heapK[i]] = [heapK[i], heapK[p]];[heapV[p], heapV[i]] = [heapV[i], heapV[p]]; i = p } }
let lastKey = 0
const pop = () => { lastKey = heapK[0]; const v = heapV[0], lk = heapK.pop()!, lv = heapV.pop()!; if (heapK.length) { heapK[0] = lk; heapV[0] = lv; let i = 0; for (;;) { const a = 2 * i + 1, b = a + 1; let m = i; if (a < heapK.length && heapK[a] < heapK[m]) m = a; if (b < heapK.length && heapK[b] < heapK[m]) m = b; if (m === i) break;[heapK[m], heapK[i]] = [heapK[i], heapK[m]];[heapV[m], heapV[i]] = [heapV[i], heapV[m]]; i = m } } return v }
// pair attraction: cells at the pair spacing beside the positive net's copper (same layer) cost less for its partner
const PAIR_PITCH = 0.28, attract = [0, 1, 2, 3].map(() => new Uint8Array(NN)), attractV = new Uint8Array(NN)
const ring = (r0: number, r1: number) => { const o: number[] = []; const k = Math.ceil(r1 / P); for (let dj = -k; dj <= k; dj++) for (let di = -k; di <= k; di++) { const d = Math.hypot(di, dj) * P; if (d >= r0 && d <= r1) o.push(di, dj) } return o }
const RING_T = ring(PAIR_PITCH - 0.06, PAIR_PITCH + 0.06), RING_V = ring(0.36, 0.55)
let attractOn = false
function setAttract(lead: Net | undefined, on: boolean) {
  if (!lead?.path) { attractOn = false; return }
  const v = on ? 1 : 0
  for (const p of lead.path) for (const id of p) { const l = (id / NN) | 0, c = id - l * NN, i = c % NX, j = (c / NX) | 0
    for (let k = 0; k < RING_T.length; k += 2) { const ii = i + RING_T[k], jj = j + RING_T[k + 1]; if (ii >= 0 && jj >= 0 && ii < NX && jj < NY) attract[l][jj * NX + ii] = v } }
  for (const c of lead.vias ?? []) { const i = c % NX, j = (c / NX) | 0
    for (let k = 0; k < RING_V.length; k += 2) { const ii = i + RING_V[k], jj = j + RING_V[k + 1]; if (ii >= 0 && jj >= 0 && ii < NX && jj < NY) attractV[jj * NX + ii] = v } }
  attractOn = on
}
const VIA_COST = 10, DIAG = Math.SQRT2, HW = +(process.env.HW ?? 1.3) // heuristic weight: > 1 trades a little path length for a much smaller search
let pres = 0.5, hard = false // hard: other nets' copper is an obstacle, not a price (endgame)
const isGoal = new Uint32Array(NL * NN)
let goalStamp = 1
/** cheapest path from any source node to any goal node (or, with goalVia, to any cell that can take a via) */
function search(n: Net, sources: number[], goals: Int32Array | null, gx0: number, gy0: number, goalVia: boolean): number[] | null {
  stamp++; goalStamp++
  heapK.length = 0; heapV.length = 0
  if (goals) for (const g of goals) isGoal[g] = goalStamp
  const wide = n.w > W_SIG, bT = n.w > W_PWR ? blockTB : wide ? blockTW : blockT
  // other nets' keep-outs in occT are sized for a 0.1 mm trace; a wider trace must also keep its extra half-width
  // clear of them, or it lands inside a thin neighbour's clearance (hard mode treats that as an obstacle)
  const extra = hard && wide ? (n.w > W_PWR ? D_EXB : D_EXW) : null
  const clearWide = (l: number, cc: number) => {
    if (!extra || neck[cc]) return true
    const i = cc % NX, j = (cc / NX) | 0, a = occT[l]
    for (let k = 0; k < extra.length; k += 2) { const ii = i + extra[k], jj = j + extra[k + 1]; if (ii >= 0 && jj >= 0 && ii < NX && jj < NY && a[jj * NX + ii]) return false }
    return true
  }
  const h = (c: number) => goalVia ? 0 : Math.hypot(wx(c % NX) - gx0, wy((c / NX) | 0) - gy0) / P * HW
  for (const s of sources) { gCost[s] = 0; from[s] = -1; seen[s] = stamp; push(h(s % NN), s) }
  let expanded = 0
  while (heapK.length) {
    const id = pop(), l = (id / NN) | 0, c = id - l * NN, g = gCost[id]
    if (lastKey > g + h(c) + 1e-4) continue // stale entry: this node was reached more cheaply since
    if (++expanded > (hard ? +(process.env.EG_CAP ?? 1.5e6) : 1.2e7)) { if (VERB) console.log("    search cap hit", expanded, "heap", heapK.length); return null }
    if (goals && isGoal[id] === goalStamp) { const out: number[] = []; for (let k = id; k !== -1; k = from[k]) out.push(k); return out.reverse() }
    const corrOk = (cc: number) => corr[cc] < 0 || corrName[corr[cc]] === n.name
    if (goalVia && !blockV[c] && !occV[c] && corrOk(c) && (!hard || !occT[l][c])) { const out: number[] = []; for (let k = id; k !== -1; k = from[k]) out.push(k); return out.reverse() }
    const i = c % NX, j = (c / NX) | 0
    if (l === 3 && !n.inner2) continue
    for (let d = 0; d < 8; d++) {
      const di = d < 4 ? [1, -1, 0, 0][d] : [1, 1, -1, -1][d - 4], dj = d < 4 ? [0, 0, 1, -1][d] : [1, -1, 1, -1][d - 4]
      const ii = i + di, jj = j + dj
      if (ii < 0 || jj < 0 || ii >= NX || jj >= NY) continue
      const cc = jj * NX + ii, nid = l * NN + cc
      if ((neck[cc] ? blockT : bT)[l][cc] && isGoal[nid] !== goalStamp) continue
      if (l === 3 && !corrOk(cc)) continue
      if (hard && (occT[l][cc] || !clearWide(l, cc)) && isGoal[nid] !== goalStamp) continue
      // the pair attraction discounts only the distance, never the price of another net's space
      const cong = (1 + histT[l][cc]) * ((attractOn && attract[l][cc] ? 0.25 : 1) + pres * occT[l][cc]) + (wide && occT[l][cc] ? 2 : 0)
      const ng = g + (d < 4 ? 1 : DIAG) * cong
      if (seen[nid] !== stamp || ng < gCost[nid]) { seen[nid] = stamp; gCost[nid] = ng; from[nid] = id; push(ng + h(cc), nid) }
    }
    if (!blockV[c] && corrOk(c)) for (let l2 = 0; l2 < NL; l2++) {
      if (l2 === l || (l2 === 3 && !n.inner2)) continue
      if (hard && occV[c]) continue
      const nid = l2 * NN + c
      if ((neck[c] ? blockT : bT)[l2][c] && isGoal[nid] !== goalStamp) continue
      const ng = g + VIA_COST * (1 + histV[c]) * ((attractOn && attractV[c] ? 0.3 : 1) + pres * occV[c])
      if (seen[nid] !== stamp || ng < gCost[nid]) { seen[nid] = stamp; gCost[nid] = ng; from[nid] = id; push(ng + h(c), nid) }
    }
  }
  if (VERB) console.log("    search exhausted after", expanded)
  return null
}
function routeNet(n: Net): boolean {
  if (n.follows) setAttract(n.follows, true)
  try {
    if (routeNet0(n)) return true
    // no path under the current prices: take the cheapest path ignoring other nets, so the net stays in the
    // negotiation as a conflict (and its neighbours learn to make room) instead of dropping out
    const keep = pres; pres = 0
    try { return routeNet0(n) } finally { pres = keep }
  } finally { if (n.follows) setAttract(n.follows, false) }
}
function routeNet0(n: Net): boolean {
  lift(n.name, -1)
  const paths: Int32Array[] = [], vias: number[] = []
  const collectVias = (p: number[]) => { for (let k = 1; k < p.length; k++) { const a = p[k - 1], b = p[k]; if ((a % NN) === (b % NN) && a !== b) vias.push(a % NN) } }
  let ok = true
  if (n.plane) {
    for (const t of n.drops) {
      const p = search(n, Array.from(t.nodes), null, t.x, t.y, true)
      if (!p) { ok = false; if (VERB) console.log("    drop failed", n.name, t.label, t.x.toFixed(2), t.y.toFixed(2)); continue }
      paths.push(Int32Array.from(p)); collectVias(p); vias.push(p[p.length - 1] % NN)
    }
  } else {
    // join the terminals one by one, nearest first, to the growing tree
    const left = [...n.terms]
    const tree: number[] = Array.from(left.shift()!.nodes)
    while (left.length) {
      const cx = tree.reduce((s, id) => s + wx((id % NN) % NX), 0) / tree.length, cy = tree.reduce((s, id) => s + wy(((id % NN) / NX) | 0), 0) / tree.length
      left.sort((a, b) => Math.hypot(a.x - cx, a.y - cy) - Math.hypot(b.x - cx, b.y - cy))
      const t = left.shift()!
      const p = search(n, tree, t.nodes, t.x, t.y, false)
      if (!p) { ok = false; continue }
      paths.push(Int32Array.from(p)); collectVias(p)
      for (const id of p) tree.push(id)
      for (const id of t.nodes) tree.push(id)
    }
  }
  lift(n.name, 1)
  n.path = paths; n.vias = [...new Set(vias)]
  return ok
}
// conflicts: a net's copper inside another net's keep-out
function conflictsOf(n: Net): number {
  if (!n.path) return 1e9
  stampNet(n, -1)
  let k = 0
  for (const p of n.path) for (const id of p) { const l = (id / NN) | 0, c = id - l * NN; if (occT[l][c]) { k++; histT[l][c] += 0.4 } }
  for (const c of n.vias!) if (occV[c]) { k++; histV[c] += 0.4 }
  stampNet(n, 1)
  return k
}
// ---------------- single-net debug ----------------
if (process.env.ONLY) {
  for (const name of process.env.ONLY.split(",")) {
    const n = nets.find((q) => q.name === name)
    console.log("terms", n?.terms.map((t) => t.label), "drops", n?.drops.length, "pads", padsByNet.get(name)?.map((p: any) => p.ref + "." + p.names[0] + " fixed=" + padTouchesFixed(p)))
    if (!n) { console.log("no net", name); continue }
    lift(n.name, -1)
    for (const t of [...n.terms, ...n.drops]) {
      const free = Array.from(t.nodes).filter((id) => { const l = (id / NN) | 0, c = id - l * NN; return !blockT[l][c] })
      const via = Array.from(t.nodes).filter((id) => !blockV[id % NN])
      // can the terminal leave its pad? count free neighbour cells within 0.3 mm on its layer
      console.log(`${name} ${t.label} (${t.x.toFixed(2)},${t.y.toFixed(2)}) cells ${t.nodes.length} free ${free.length} viaOK ${via.length}`)
    }
    lift(n.name, 1)
    // plain reachability flood from each terminal (no costs), to tell a sealed-in pad from a search limit
    lift(n.name, -1)
    for (const t of [...n.terms, ...n.drops]) {
      const seenR = new Uint8Array(NL * NN), q: number[] = Array.from(t.nodes); for (const id of q) seenR[id] = 1
      let qi = 0, bbx = [1e9, 1e9, -1e9, -1e9]
      while (qi < q.length) { const id = q[qi++], l = (id / NN) | 0, c = id - l * NN, i = c % NX, j = (c / NX) | 0
        const x = wx(i), y = wy(j); bbx = [Math.min(bbx[0], x), Math.min(bbx[1], y), Math.max(bbx[2], x), Math.max(bbx[3], y)]
        for (const [di, dj] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) { const ii = i + di, jj = j + dj; if (ii < 0 || jj < 0 || ii >= NX || jj >= NY) continue; const cc = jj * NX + ii, nid = l * NN + cc; if (!seenR[nid] && !blockT[l][cc]) { seenR[nid] = 1; q.push(nid) } }
        if (!blockV[c]) for (let l2 = 0; l2 < NL; l2++) { const nid = l2 * NN + c; if (!seenR[nid] && !blockT[l2][c]) { seenR[nid] = 1; q.push(nid) } } }
      console.log(`  reach from ${t.label}: ${q.length} nodes, bbox ${bbx.map((v) => v.toFixed(1)).join(",")}`)
    }
    for (const t of n.terms.filter((t) => t.label === "via").slice(0, 1)) {
      const c = t.nodes[0] % NN
      console.log("  blockers of via", t.x, t.y, "inner2 count", blockT[3][c], "top", blockT[0][c])
      for (const o of objs) if (o.t!.includes(c)) console.log("   ", o.net, o.layers.join(""), o.shape.kind, o.shape.x.toFixed(2), o.shape.y.toFixed(2), (o.shape.r ?? o.shape.w)?.toFixed(3))
    }
    lift(n.name, 1)
    const t1 = performance.now(), ok = routeNet(n)
    console.log(name, ok ? "routed" : "FAILED", ((performance.now() - t1) / 1e3).toFixed(1) + "s")
  }
  process.exit(0)
}
async function writeOut(routesPath: string, copperPath: string) {
  const routes: any = {}
  for (const n of nets) routes[n.name] = geometry(n)
  // conflict spots: cells of a net's copper inside another net's keep-out
  const spots: any[] = []
  for (const n of nets) if (n.conflicts && n.path) { stampNet(n, -1); for (const p of n.path) for (const id of p) { const l = (id / NN) | 0, c = id - l * NN; if (occT[l][c]) spots.push([+wx(c % NX).toFixed(2), +wy((c / NX) | 0).toFixed(2), l, n.name]) } stampNet(n, 1) }
  await Bun.write(routesPath, JSON.stringify({ failed, conflicts: nets.filter((n) => n.conflicts).map((n) => n.name), spots, nets: routes }))
  const copper = { traces: [...fixed.traces, ...Object.values(routes).flatMap((r: any) => r.segs)], vias: [...fixed.vias, ...Object.values(routes).flatMap((r: any) => r.vias)] }
  await Bun.write(copperPath, JSON.stringify(copper))
}
if (process.env.PLANES_ONLY) for (let k = nets.length - 1; k >= 0; k--) if (!nets[k].plane) nets.splice(k, 1)
// ---------------- negotiation ----------------
const t0 = performance.now()
nets.sort((a, b) => (a.plane ? 1 : 0) - (b.plane ? 1 : 0) || a.order - b.order)
// a follower right after its lead
{ const followers = nets.filter((n) => n.follows); for (const f of followers) { nets.splice(nets.indexOf(f), 1); nets.splice(nets.indexOf(f.follows!) + 1, 0, f) } }
console.log(`grid ${NX}x${NY}, ${nets.length} nets (${nets.filter((n) => n.plane).length} plane drop sets, ${nets.reduce((s, n) => s + n.terms.length + n.drops.length, 0)} terminals)`)
// ---------------- endgame ----------------
// Negotiation stalls on a few deadlocks that need several nets to move together. Rip up the nets in conflict and
// every net passing near a conflict, then place them back one at a time with everything else as hard obstacles,
// trying several orders until one fits them all. On failure the previous routes are restored.
function endgame(bad: Net[], tries: number): boolean {
  const spots: number[] = []
  for (const n of bad) { if (!n.path) continue; stampNet(n, -1); for (const p of n.path) for (const id of p) { const l = (id / NN) | 0, c = id - l * NN; if (occT[l][c]) spots.push(c) } stampNet(n, 1) }
  const R = Math.round(1.2 / P), near = new Uint8Array(NN)
  for (const c of spots) { const i = c % NX, j = (c / NX) | 0; for (let dj = -R; dj <= R; dj += 2) for (let di = -R; di <= R; di += 2) { const ii = i + di, jj = j + dj; if (ii >= 0 && jj >= 0 && ii < NX && jj < NY) near[jj * NX + ii] = 1 } }
  const set = new Set<Net>(bad)
  for (const n of nets) if (n.path && n.path.some((p) => p.some((id) => near[id % NN]))) set.add(n)
  for (const n of [...set]) { if (n.partner) set.add(n.partner); if (n.follows) set.add(n.follows) }
  const group = nets.filter((n) => set.has(n))
  const saved = new Map(group.map((n) => [n, { path: n.path, vias: n.vias }]))
  const before = groupConflicts(group)
  let bestT = Infinity, bestA = -1, best: Map<Net, { path: any; vias: any }> | null = null
  for (const n of group) stampNet(n, -1)
  const span = (n: Net) => { const ts = [...n.terms, ...n.drops]; const xs = ts.map((t) => t.x), ys = ts.map((t) => t.y); return Math.max(...xs) - Math.min(...xs) + Math.max(...ys) - Math.min(...ys) }
  for (let a = 0; a < tries; a++) {
    let order = a === 0 ? [...group].sort((x, y) => span(y) - span(x)) : [...group].sort(() => rand() - 0.5)
    // keep each pair's lead right before its follower
    order = order.filter((n) => !n.follows); for (const f of group.filter((n) => n.follows)) { const k = order.indexOf(f.follows!); order.splice(k < 0 ? order.length : k + 1, 0, f) }
    hard = true
    const placed: Net[] = []
    for (const n of order) {
      // no conflict-free path with everything else fixed: route it normally (priced), so the order still counts
      if (!routeNet0Hard(n)) { hard = false; routeNet(n); hard = true }
      stampNet(n, 1); placed.push(n)
    }
    hard = false
    const t = groupConflicts(group)
    if (t < bestT) { bestT = t; bestA = a; best = new Map(group.map((n) => [n, { path: n.path, vias: n.vias }])) }
    for (const n of placed) stampNet(n, -1)
    if (bestT === 0) break
  }
  // keep the best order if it beats what was there, else put the old routes back
  const keep = bestT < before ? best! : saved
  for (const n of group) { const sv = keep.get(n)!; n.path = sv.path; n.vias = sv.vias; stampNet(n, 1) }
  if (bestT < before) console.log(`  endgame: ${group.length} nets around ${bad.length}: conflicts ${before} -> ${bestT} (order ${bestA})`)
  else console.log(`  endgame: no better order for ${group.length} nets in ${tries} tries (${before})`)
  return bestT < before
}
// conflicts of a group's nets with anything (no side effects on the history costs)
function groupConflicts(group: Net[]): number {
  let k = 0
  for (const n of group) {
    if (!n.path) { k += 1000; continue }
    stampNet(n, -1)
    for (const p of n.path) for (const id of p) { const l = (id / NN) | 0, c = id - l * NN; if (occT[l][c]) k++ }
    for (const c of n.vias!) if (occV[c]) k++
    stampNet(n, 1)
  }
  return k
}
// the conflicts fall into separate places on the board; re-place each place's nets on their own, so one
// crowded spot cannot sink the re-placement of the others
function endgameClusters(bad: Net[], tries: number): number {
  const B = Math.round(1.0 / P), key = (c: number) => (((c / NX) | 0) / B | 0) * 100000 + ((c % NX) / B | 0)
  const parent = bad.map((_, i) => i), find = (a: number): number => (parent[a] === a ? a : (parent[a] = find(parent[a])))
  const owner = new Map<number, number>()
  bad.forEach((n, i) => {
    if (!n.path) return
    stampNet(n, -1)
    for (const p of n.path) for (const id of p) {
      const l = (id / NN) | 0, c = id - l * NN
      if (!occT[l][c]) continue
      const k0 = key(c)
      for (const dk of [0, 1, -1, 100000, -100000, 100001, -100001, 99999, -99999]) { const o = owner.get(k0 + dk); if (o !== undefined) parent[find(o)] = find(i) }
      owner.set(k0, i)
    }
    stampNet(n, 1)
  })
  const groups = new Map<number, Net[]>()
  bad.forEach((n, i) => { const r = find(i); if (!groups.has(r)) groups.set(r, []); groups.get(r)!.push(n) })
  const list = [...groups.values()].sort((a, b) => a.length - b.length)
  let fixed = 0
  for (const g of list) {
    const live = g.filter((n) => conflictsOf(n) > 0)
    // a big cluster gets fewer orders: each failed order costs a full search per net
    if (live.length && endgame(live, live.length > 6 ? Math.max(4, tries >> 2) : tries)) fixed++
  }
  console.log(`  endgame: ${fixed} of ${list.length} conflict clusters re-placed`)
  return fixed
}
function routeNet0Hard(n: Net): boolean {
  if (n.follows) setAttract(n.follows, true)
  try { return routeNet0(n) } finally { if (n.follows) setAttract(n.follows, false) }
}
let failed: string[] = []
let dirty = nets
let best = Infinity, bestAt = 0
let bestSnap: Map<Net, { path: any; vias: any }> | null = null
for (let it = 0; it < MAXIT; it++) {
  failed = []
  for (const n of dirty) { stampNet(n, -1); if (!routeNet(n)) failed.push(n.name); stampNet(n, 1) }
  let total = 0; const bad: Net[] = []
  for (const n of nets) { n.conflicts = conflictsOf(n); if (n.conflicts) { total += n.conflicts; bad.push(n) } }
  console.log(`iter ${it} [${((performance.now() - t0) / 1e3).toFixed(0)}s] pres=${pres.toFixed(2)} conflicts=${total} nets=${bad.length} ${bad.slice(0, 8).map((n) => n.name).join(",")} failed=${failed.length} ${failed.slice(0, 6).join(",")}`)
  if (!total && !failed.length) break
  if (it % 10 === 9) await writeOut(dir + `/routes${process.env.OUT ?? ""}.ckpt.json`, dir + `/copper${process.env.OUT ?? ""}.ckpt.json`)
  if (total < best) { best = total; bestAt = it; bestSnap = new Map(nets.map((n) => [n, { path: n.path, vias: n.vias }])) }
  if (it - bestAt >= +(process.env.STALL ?? 4) && bestSnap) {
    // no progress for a while (or diverging): go back to the best routing seen, then re-place its conflict clusters
    if (total > best) {
      for (const n of nets) stampNet(n, -1)
      for (const n of nets) { const sv = bestSnap.get(n)!; n.path = sv.path; n.vias = sv.vias; stampNet(n, 1) }
      console.log(`  back to the best routing (pass ${bestAt}, ${best} conflicts)`)
    }
    let b2: Net[] = []
    for (const n of nets) { n.conflicts = conflictsOf(n); if (n.conflicts) b2.push(n) }
    endgameClusters(b2, +(process.env.EG_TRIES ?? 24))
    let t2 = 0; bad.length = 0
    for (const n of nets) { n.conflicts = conflictsOf(n); if (n.conflicts) { t2 += n.conflicts; bad.push(n) } }
    console.log(`  after endgame: conflicts=${t2}`)
    if (!t2 && !failed.length) break
    best = t2; bestAt = it; bestSnap = new Map(nets.map((n) => [n, { path: n.path, vias: n.vias }]))
  }
  const want = new Set(bad.concat(nets.filter((n) => failed.includes(n.name))))
  for (const n of [...want]) { if (n.partner) want.add(n.partner); if (n.follows) want.add(n.follows) }
  dirty = nets.filter((n) => want.has(n))
  pres = Math.min(pres * +(process.env.PG ?? 1.3), +(process.env.PMAX ?? 20))
}
// ---------------- output ----------------
function geometry(n: Net) {
  const segs: any[] = [], vs = (n.vias ?? []).map((c) => ({ x: +wx(c % NX).toFixed(4), y: +wy((c / NX) | 0).toFixed(4), d: VIA_D, hole: VIA_H, net: n.name }))
  for (const p of n.path ?? []) {
    let run: number[] = []
    const flush = () => {
      if (run.length < 2) { run = []; return }
      const l = (run[0] / NN) | 0, pts = run.map((id) => ({ x: +wx((id % NN) % NX).toFixed(4), y: +wy(((id % NN) / NX) | 0).toFixed(4) }))
      const simp = pts.filter((q, k) => k === 0 || k === pts.length - 1 || (pts[k + 1].x - q.x) * (q.y - pts[k - 1].y) !== (pts[k + 1].y - q.y) * (q.x - pts[k - 1].x))
      const narrow = n.w > W_SIG && run.some((id) => neck[id % NN])
      segs.push({ layer: LAYERS[l], pts: simp, w: narrow ? W_SIG : n.w, net: n.name }); run = []
    }
    for (let k = 0; k < p.length; k++) {
      if (k && ((p[k] / NN) | 0) !== ((p[k - 1] / NN) | 0)) flush()
      else if (k && n.w > W_SIG && neck[p[k] % NN] !== neck[p[k - 1] % NN]) { run.push(p[k]); flush() }
      run.push(p[k])
    }
    flush()
  }
  return { segs, vias: vs }
}
const OUT = process.env.OUT ?? ""
await writeOut(dir + `/routes${OUT}.json`, dir + `/copper${OUT}.json`)
const ok = !failed.length && !nets.some((n) => n.conflicts)
console.log(ok ? "SOLVED" : `NOT SOLVED: failed ${failed.length}, in conflict ${nets.filter((n) => n.conflicts).length}`, `${((performance.now() - t0) / 1e3).toFixed(0)}s`)
