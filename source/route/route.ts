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

// ---------------- rules ----------------
const P = 0.05, GAP = 0.1, W_SIG = 0.1, W_PWR = 0.2, VIA_D = 0.25, VIA_H = 0.15, EDGE = 0.3, EPS = 0.004
// inner2 is the power plane layer; small supply rails may also run there as traces (the plane islands avoid them)
const LAYERS = ["top", "inner3", "bottom", "inner2"] as const, NL = 4
const B = padsIn.board, X0 = B.x0, Y0 = B.y0
const NX = Math.round((B.x1 - B.x0) / P) + 1, NY = Math.round((B.y1 - B.y0) / P) + 1, NN = NX * NY
const gx = (x: number) => Math.round((x - X0) / P), gy = (y: number) => Math.round((y - Y0) / P)
const wx = (i: number) => X0 + i * P, wy = (j: number) => Y0 + j * P
const HOLES = [[0, 0], [33, 0], [0, -48], [33, -48]], HOLE_R = 1.35
const PLANE_GND = new Set(["GND"])
const PLANE_PWR = new Set(["VDD_CPU", "VDD_LOGIC", "VDD_GPU", "VDD_NPU", "VCC_DDR", "VCC3V3_SYS", "VCC5V0_SYS"])
const isPlane = (n: string) => PLANE_GND.has(n) || PLANE_PWR.has(n)
const widthOf = (n: string) => (!isPlane(n) && /^(VCC|VDD)/.test(n) ? W_PWR : W_SIG)
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
type Obj = { net: string | null; layers: number[]; shape: Shape; t?: Int32Array; tw?: Int32Array; v?: Int32Array; pad?: any }
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

const blockT = [0, 1, 2, 3].map(() => new Uint16Array(NN)), blockTW = [0, 1, 2, 3].map(() => new Uint16Array(NN)), blockV = new Uint16Array(NN)
const R_T = GAP + W_SIG / 2, R_TW = GAP + W_PWR / 2, R_V = GAP + VIA_D / 2
for (const o of objs) {
  o.t = Int32Array.from(cellsWithin(o.shape, R_T)); o.tw = Int32Array.from(cellsWithin(o.shape, R_TW)); o.v = Int32Array.from(cellsWithin(o.shape, R_V))
  for (const l of o.layers) { for (const c of o.t) blockT[l][c]++; for (const c of o.tw) blockTW[l][c]++ }
  for (const c of o.v) blockV[c]++
}
// board edge and mounting holes
for (let j = 0; j < NY; j++) for (let i = 0; i < NX; i++) {
  const x = wx(i), y = wy(j), c = j * NX + i
  const de = Math.min(x - B.x0, B.x1 - x, y - B.y0, B.y1 - y), dh = Math.min(...HOLES.map(([hx, hy]) => Math.hypot(x - hx, y - hy) - HOLE_R))
  const d = Math.min(de, dh)
  if (d < EDGE + W_SIG / 2) for (let l = 0; l < NL; l++) blockT[l][c] += 1000
  if (d < EDGE + W_PWR / 2) for (let l = 0; l < NL; l++) blockTW[l][c] += 1000
  if (d < EDGE + VIA_D / 2) blockV[c] += 1000
}
// neck-down zones: inside a BGA ball field a power trace narrows to signal width
const neck = new Uint8Array(NN)
{
  const bgas = new Map<string, number[]>()
  for (const p of padsIn.pads) if (["U1", "U2", "U6"].includes(p.ref)) { const b = bgas.get(p.ref) ?? [1e9, 1e9, -1e9, -1e9]; bgas.set(p.ref, [Math.min(b[0], p.x), Math.min(b[1], p.y), Math.max(b[2], p.x), Math.max(b[3], p.y)]) }
  for (const [, b] of bgas) for (let j = gy(b[1] - 0.6); j <= gy(b[3] + 0.6); j++) for (let i = gx(b[0] - 0.6); i <= gx(b[2] + 0.6); i++) if (i >= 0 && j >= 0 && i < NX && j < NY) neck[j * NX + i] = 1
}
const objsByNet = new Map<string, Obj[]>()
for (const o of objs) if (o.net) (objsByNet.get(o.net) ?? objsByNet.set(o.net, []).get(o.net)!).push(o)
function lift(net: string, s: 1 | -1) {
  for (const o of objsByNet.get(net) ?? []) {
    for (const l of o.layers) { for (const c of o.t!) blockT[l][c] += s; for (const c of o.tw!) blockTW[l][c] += s }
    for (const c of o.v!) blockV[c] += s
  }
}

// ---------------- nets and terminals ----------------
// A terminal is a set of graph nodes (layer * NN + cell): a pad's cells on its layer, or a via's cell on all layers.
type Term = { nodes: Int32Array; x: number; y: number; label: string }
type Net = { name: string; w: number; plane: boolean; inner2?: boolean; terms: Term[]; drops: Term[]; path?: Int32Array[]; vias?: number[]; conflicts?: number; order: number }
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
  if (name.startsWith("DDR_")) continue // routed LPDDR4 block
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
  if (terms.length >= 2) nets.push({ name, w: widthOf(name), plane: false, inner2: /^(VCC|VDD)/.test(name), terms, drops: [], order: rand() })
}
// ---------------- occupancy (other nets' routed copper) ----------------
const occT = [0, 1, 2, 3].map(() => new Uint16Array(NN)), occV = new Uint16Array(NN)
const histT = [0, 1, 2, 3].map(() => new Float32Array(NN)), histV = new Float32Array(NN)
const disk = (r: number) => { const o: number[] = []; const k = Math.ceil(r / P); for (let dj = -k; dj <= k; dj++) for (let di = -k; di <= k; di++) if (Math.hypot(di, dj) * P < r - EPS) o.push(di, dj); return o }
const D_TT = disk(W_SIG + GAP + 0.0), D_TTW = disk(W_PWR / 2 + W_SIG / 2 + GAP), D_TV = disk(W_SIG / 2 + GAP + VIA_D / 2), D_VV = disk(VIA_D + GAP)
const D_WTV = disk(W_PWR / 2 + GAP + VIA_D / 2)
function stampDisk(arr: Uint16Array, c: number, offs: number[], s: number) {
  const i = c % NX, j = (c / NX) | 0
  for (let k = 0; k < offs.length; k += 2) { const ii = i + offs[k], jj = j + offs[k + 1]; if (ii >= 0 && jj >= 0 && ii < NX && jj < NY) arr[jj * NX + ii] += s }
}
function stampNet(n: Net, s: 1 | -1) {
  if (!n.path) return
  const DT = n.w > W_SIG ? D_TTW : D_TT, DTV = n.w > W_SIG ? D_WTV : D_TV
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
const VIA_COST = 10, DIAG = Math.SQRT2, HW = +(process.env.HW ?? 1.3) // heuristic weight: > 1 trades a little path length for a much smaller search
let pres = 0.5
const isGoal = new Uint32Array(NL * NN)
let goalStamp = 1
/** cheapest path from any source node to any goal node (or, with goalVia, to any cell that can take a via) */
function search(n: Net, sources: number[], goals: Int32Array | null, gx0: number, gy0: number, goalVia: boolean): number[] | null {
  stamp++; goalStamp++
  heapK.length = 0; heapV.length = 0
  if (goals) for (const g of goals) isGoal[g] = goalStamp
  const wide = n.w > W_SIG, bT = wide ? blockTW : blockT
  const h = (c: number) => goalVia ? 0 : Math.hypot(wx(c % NX) - gx0, wy((c / NX) | 0) - gy0) / P * HW
  for (const s of sources) { gCost[s] = 0; from[s] = -1; seen[s] = stamp; push(h(s % NN), s) }
  let expanded = 0
  while (heapK.length) {
    const id = pop(), l = (id / NN) | 0, c = id - l * NN, g = gCost[id]
    if (lastKey > g + h(c) + 1e-4) continue // stale entry: this node was reached more cheaply since
    if (++expanded > 1.2e7) { if (VERB) console.log("    search cap hit", expanded, "heap", heapK.length); return null }
    if (goals && isGoal[id] === goalStamp) { const out: number[] = []; for (let k = id; k !== -1; k = from[k]) out.push(k); return out.reverse() }
    if (goalVia && !blockV[c] && !occV[c]) { const out: number[] = []; for (let k = id; k !== -1; k = from[k]) out.push(k); return out.reverse() }
    const i = c % NX, j = (c / NX) | 0
    if (l === 3 && !n.inner2) continue
    for (let d = 0; d < 8; d++) {
      const di = d < 4 ? [1, -1, 0, 0][d] : [1, 1, -1, -1][d - 4], dj = d < 4 ? [0, 0, 1, -1][d] : [1, -1, 1, -1][d - 4]
      const ii = i + di, jj = j + dj
      if (ii < 0 || jj < 0 || ii >= NX || jj >= NY) continue
      const cc = jj * NX + ii, nid = l * NN + cc
      if ((neck[cc] ? blockT : bT)[l][cc] && isGoal[nid] !== goalStamp) continue
      const cong = (1 + histT[l][cc]) * (1 + pres * occT[l][cc]) + (wide && occT[l][cc] ? 2 : 0)
      const ng = g + (d < 4 ? 1 : DIAG) * cong
      if (seen[nid] !== stamp || ng < gCost[nid]) { seen[nid] = stamp; gCost[nid] = ng; from[nid] = id; push(ng + h(cc), nid) }
    }
    if (!blockV[c]) for (let l2 = 0; l2 < NL; l2++) {
      if (l2 === l || (l2 === 3 && !n.inner2)) continue
      const nid = l2 * NN + c
      if ((neck[c] ? blockT : bT)[l2][c] && isGoal[nid] !== goalStamp) continue
      const ng = g + VIA_COST * (1 + histV[c]) * (1 + pres * occV[c])
      if (seen[nid] !== stamp || ng < gCost[nid]) { seen[nid] = stamp; gCost[nid] = ng; from[nid] = id; push(ng + h(c), nid) }
    }
  }
  if (VERB) console.log("    search exhausted after", expanded)
  return null
}
function routeNet(n: Net): boolean {
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
// ---------------- negotiation ----------------
const t0 = performance.now()
nets.sort((a, b) => (a.plane ? 1 : 0) - (b.plane ? 1 : 0) || a.order - b.order)
console.log(`grid ${NX}x${NY}, ${nets.length} nets (${nets.filter((n) => n.plane).length} plane drop sets, ${nets.reduce((s, n) => s + n.terms.length + n.drops.length, 0)} terminals)`)
let failed: string[] = []
let dirty = nets
for (let it = 0; it < MAXIT; it++) {
  failed = []
  for (const n of dirty) { stampNet(n, -1); if (!routeNet(n)) failed.push(n.name); stampNet(n, 1) }
  let total = 0; const bad: Net[] = []
  for (const n of nets) { n.conflicts = conflictsOf(n); if (n.conflicts) { total += n.conflicts; bad.push(n) } }
  console.log(`iter ${it} [${((performance.now() - t0) / 1e3).toFixed(0)}s] pres=${pres.toFixed(2)} conflicts=${total} nets=${bad.length} ${bad.slice(0, 8).map((n) => n.name).join(",")} failed=${failed.length} ${failed.slice(0, 6).join(",")}`)
  if (!total && !failed.length) break
  if (it % 10 === 9) await writeOut(dir + "/routes.ckpt.json", dir + "/copper.ckpt.json")
  dirty = bad.concat(nets.filter((n) => failed.includes(n.name) && !bad.includes(n)))
  pres = Math.min(pres * 1.6, 200)
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
await writeOut(dir + "/routes.json", dir + "/copper.json")
const ok = !failed.length && !nets.some((n) => n.conflicts)
console.log(ok ? "SOLVED" : `NOT SOLVED: failed ${failed.length}, in conflict ${nets.filter((n) => n.conflicts).length}`, `${((performance.now() - t0) / 1e3).toFixed(0)}s`)
