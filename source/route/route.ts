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
// ECO: FROZEN=frozen.json holds the finished copper of nets that a change did not touch; it is fixed copper here and
// those nets are not routed again (eco_prepare.py decides which nets stay)
const frozenNets = new Set<string>()
if (process.env.FROZEN) {
  const fz = await Bun.file(process.env.FROZEN).json()
  fixed.traces.push(...fz.traces); fixed.vias.push(...fz.vias)
  for (const t of [...fz.traces, ...fz.vias]) frozenNets.add(t.net)
}

// ---------------- rules ----------------
const P = 0.05, GAP = 0.1 + 0.012, W_SIG = 0.1, W_PWR = +(process.env.W_PWR ?? 0.2), W_BIG = +(process.env.W_BIG ?? 0.4), VIA_D = 0.25, VIA_H = 0.15, EDGE = 0.3, EPS = 0.004
// JLCPCB: a via's drilled hole keeps 0.2 mm from copper of other nets (inner layers included), so the copper gap
// around a 0.15/0.25 mm via is 0.2 - (0.25 - 0.15) / 2 = 0.15 mm, not the 0.1 mm trace-to-trace gap
const VGAP = process.env.HOLE_RULE ? Math.max(GAP, 0.2 + 0.012 - (VIA_D - VIA_H) / 2) : GAP  // HOLE_RULE=1: enforce it
// inner2 is the power plane layer; small supply rails may also run there as traces (the plane islands avoid them)
// GND_SIG: slow signals may also cross the ground layers (inner1 under top, inner4 above bottom) where no fast signal
// runs on the adjacent outer layer, so every fast trace keeps an unbroken reference plane
const GND_SIG = !!process.env.GND_SIG
const LAYERS = ["top", "inner3", "bottom", "inner2", "inner1", "inner4"] as const, NL = GND_SIG ? 6 : 4
const ALL_L = Array.from({ length: NL }, (_, i) => i)
const B = padsIn.board, X0 = B.x0, Y0 = B.y0
const NX = Math.round((B.x1 - B.x0) / P) + 1, NY = Math.round((B.y1 - B.y0) / P) + 1, NN = NX * NY
const gx = (x: number) => Math.round((x - X0) / P), gy = (y: number) => Math.round((y - Y0) / P)
const wx = (i: number) => X0 + i * P, wy = (j: number) => Y0 + j * P
const HOLES = [[0, 0], [33, 0], [0, -48], [33, -48]], HOLE_R = 1.35
const PLANE_GND = new Set(["GND"])
const PLANE_PWR = new Set(["VDD_CPU", "VDD_LOGIC", "VDD_GPU", "VDD_NPU", "VCC_DDR", "VCC0V6_DDR"])
const isPlane = (n: string) => PLANE_GND.has(n) || PLANE_PWR.has(n)
// buck switch nodes and the 5 V / 3.3 V input rails carry 1-3 A: widest class; other supplies the middle class
const widthOf = (n: string) => (["VCC3V3_SYS", "VCC5V0_SYS"].includes(n) || /^SW(\d|_)/.test(n) ? W_BIG : !isPlane(n) && /^(VCC|VDD)/.test(n) ? W_PWR : W_SIG)
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
const L_OF: Record<string, number> = GND_SIG ? { top: 0, inner3: 1, bottom: 2, inner2: 3, inner1: 4, inner4: 5 } : { top: 0, inner3: 1, bottom: 2, inner2: 3 }
for (const p of padsIn.pads) {
  const l = L_OF[p.layer]
  const shape: Shape = p.shape === "circle" ? { kind: "circle", x: p.x, y: p.y, r: p.w / 2 } : { kind: "rect", x: p.x, y: p.y, w: p.w, h: p.h }
  objs.push({ net: p.net, layers: [l], shape, pad: p })
}
for (const v of padsIn.footprintVias) objs.push({ net: "GND", via: true, hole: v.hole, d: v.d, layers: ALL_L, shape: { kind: "circle", x: v.x, y: v.y, r: v.d / 2 } })
for (const t of fixed.traces) {
  const l = L_OF[t.layer]
  if (l === undefined) continue // plane-layer stubs of the fanout
  for (let i = 1; i < t.pts.length; i++)
    objs.push({ net: t.net, layers: [l], shape: { kind: "seg", x: t.pts[i - 1].x, y: t.pts[i - 1].y, x2: t.pts[i].x, y2: t.pts[i].y, r: t.w / 2 } })
}
for (const v of fixed.vias) objs.push({ net: v.net, via: true, hole: v.hole, d: v.d, layers: ALL_L, shape: { kind: "circle", x: v.x, y: v.y, r: v.d / 2 } })

const blockT = ALL_L.map(() => new Uint16Array(NN)), blockTW = ALL_L.map(() => new Uint16Array(NN)), blockTB = ALL_L.map(() => new Uint16Array(NN)), blockV = new Uint16Array(NN)
const R_T = GAP + W_SIG / 2, R_TW = GAP + W_PWR / 2, R_TB = GAP + W_BIG / 2, R_V = VGAP + VIA_D / 2
for (const o of objs) {
  const xg = o.via && process.env.HOLE_RULE ? Math.max(0, 0.2 + 0.012 - (o.d - o.hole) / 2 - GAP) : 0  // a fixed via's hole keeps 0.2 mm from new copper too
  o.t = Int32Array.from(cellsWithin(o.shape, R_T + xg)); o.tw = Int32Array.from(cellsWithin(o.shape, R_TW + xg)); o.tb = Int32Array.from(cellsWithin(o.shape, R_TB + xg)); o.v = Int32Array.from(cellsWithin(o.shape, R_V + xg))
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
const neck = new Uint8Array(NN), bgaBox = new Map<string, number[]>()
{
  const bgas = bgaBox
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
// ground layers (GND_SIG): kept solid under the BGA / fine-pitch fields and under the routed DDR copper (fast: the
// DDR traces on top reference inner1, those on the bottom inner4)
if (GND_SIG) {
  const blk = (l: number, c: number) => { blockT[l][c] += 1000; blockTW[l][c] += 1000; blockTB[l][c] += 1000 }
  // GND_SIG_BGA: the ground layers under the SoC ball field also take slow signals (still never next to a fast trace);
  // the other BGA / fine-pitch fields keep solid ground layers
  const socBox = bgaBox.get("U1")
  for (let c = 0; c < NN; c++) if (neck[c]) {
    const x = wx(c % NX), y = wy((c / NX) | 0)
    if (process.env.GND_SIG_BGA && socBox && x >= socBox[0] - 0.6 && x <= socBox[2] + 0.6 && y >= socBox[1] - 0.6 && y <= socBox[3] + 0.6) continue
    blk(4, c); blk(5, c)
  }
  const RR = W_SIG / 2 + 3 * 0.0764 + W_SIG / 2 + GAP
  let n = 0
  for (const t of fixed.traces) {
    // fixed copper of a fast net (the DDR block, and kept fast traces of an ECO) needs its reference plane too
    if (!(t.net.startsWith("DDR_") || /^(HDMI_TX_[CD]|MIPI_|PCIE20_|USB_OTG0_D|EMMC_|CM4_SD_)/.test(t.net)) || (t.layer !== "top" && t.layer !== "bottom")) continue
    const l = t.layer === "top" ? 4 : 5
    for (let i = 1; i < t.pts.length; i++) for (const c of cellsWithin({ kind: "seg", x: t.pts[i - 1].x, y: t.pts[i - 1].y, x2: t.pts[i].x, y2: t.pts[i].y, r: t.w / 2 }, RR)) { blk(l, c); n++ }
  }
  console.log("ground layers open to slow signals; kept solid under BGAs and", n, "DDR reference cells")
}
// inner2 corridors of the supply islands (planes.py, from a plane-drops-only run): another net's via there would
// cut the island off from its regulator, so only the rail's own vias may go there (outside the BGA fields)
const corr = new Int16Array(NN).fill(-1), corrName: string[] = []
// the SoC ball field: there the island feeds are deliberately thin and run between the ball vias, so they are not
// enforced as corridors; everywhere else (other parts' fine-pitch zones included) they are
const SOCB = bgaBox.get("U1")!
const socField = (c: number) => { const x = wx(c % NX), y = wy((c / NX) | 0); return x >= SOCB[0] - 0.6 && x <= SOCB[2] + 0.6 && y >= SOCB[1] - 0.6 && y <= SOCB[3] + 0.6 }
if (!process.env.PLANES_ONLY && (await Bun.file(dir + "/corridors.json").exists())) {
  const cs = await Bun.file(dir + "/corridors.json").json()
  for (const c of cs) {
    const id = corrName.length; corrName.push(c.net)
    for (const [x, y] of c.cells) { const i = gx(x), j = gy(y); if (i >= 0 && j >= 0 && i < NX && j < NY && !socField(j * NX + i) && corr[j * NX + i] < 0) corr[j * NX + i] = id }
  }
  console.log("corridors", cs.length, "cells", corr.reduce((s, v) => s + (v >= 0 ? 1 : 0), 0))
  // INNER2_OPEN: between the SoC and the RK809 the islands keep only their feed corridors (widened by KEEP on each
  // side, so every feed stays >= CORR + 2 KEEP wide); slow signals may use the rest of inner2 there
  if (process.env.INNER2_OPEN) {
    // the widened feed corridors apply on the whole board: wherever inner2 takes slow traces (south of the SoC and
    // everywhere outside the island boxes) an island keeps a full-width connection to its regulator
    const KEEP = Math.round(+(process.env.KEEP ?? 0.3) / P)
    let n = 0
    for (let j = 0; j < NY; j++) for (let i = 0; i < NX; i++) {
      if (socField(j * NX + i)) continue
      let hit = false
      for (let dj = -KEEP; dj <= KEEP && !hit; dj++) for (let di = -KEEP; di <= KEEP; di++) { const ii = i + di, jj = j + dj; if (ii >= 0 && jj >= 0 && ii < NX && jj < NY && corr[jj * NX + ii] >= 0) { hit = true; break } }
      if (hit) { const c = j * NX + i; blockT[3][c] += 1000; blockTW[3][c] += 1000; blockTB[3][c] += 1000; n++ }
    }
    console.log("inner2 open to slow traces outside the islands; widened feed corridors:", n, "cells")
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
type Net = { name: string; w: number; plane: boolean; inner2?: boolean; fast?: boolean; gnd?: boolean; decoupled?: boolean; partner?: Net; follows?: Net; terms: Term[]; drops: Term[]; path?: Int32Array[]; vias?: number[]; conflicts?: number; order: number }
const padTerm = (p: any): Term => {
  const l = L_OF[p.layer]
  const shape: Shape = p.shape === "circle" ? { kind: "circle", x: p.x, y: p.y, r: p.w / 2 } : { kind: "rect", x: p.x, y: p.y, w: p.w, h: p.h }
  let cells = cellsWithin(shape, 0)
  if (!cells.length) cells = [gy(p.y) * NX + gx(p.x)]
  return { nodes: Int32Array.from(cells.map((c) => l * NN + c)), x: p.x, y: p.y, label: `${p.ref}.${p.names[0]}` }
}
const viaTerm = (v: any): Term => { const c = gy(v.y) * NX + gx(v.x); return { nodes: Int32Array.from(ALL_L.map((l) => l * NN + c)), x: v.x, y: v.y, label: "via" } }
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
  if (frozenNets.has(name) && !isPlane(name)) continue // ECO: finished copper kept as it is (a plane net routes its open pads)
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
  // ground-layer crossings: slow nets up to small-rail width only (wide supply traces would cut the plane too much)
  if (terms.length >= 2) nets.push({ name, w: widthOf(name), plane: false, inner2: !fast, fast, gnd: GND_SIG && !fast && widthOf(name) <= W_PWR, terms, drops: [], order: rand() })
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
const occT = ALL_L.map(() => new Uint16Array(NN)), occV = new Uint16Array(NN)
const histT = ALL_L.map(() => new Float32Array(NN)), histV = new Float32Array(NN)
const disk = (r: number) => { const o: number[] = []; const k = Math.ceil(r / P); for (let dj = -k; dj <= k; dj++) for (let di = -k; di <= k; di++) if (Math.hypot(di, dj) * P < r - EPS) o.push(di, dj); return o }
const D_TT = disk(W_SIG + GAP + 0.0), D_TTW = disk(W_PWR / 2 + W_SIG / 2 + GAP), D_TTB = disk(W_BIG / 2 + W_SIG / 2 + GAP), D_BTV = disk(W_BIG / 2 + VGAP + VIA_D / 2), D_TV = disk(W_SIG / 2 + VGAP + VIA_D / 2), D_VV = disk(VIA_D + VGAP)
const D_WTV = disk(W_PWR / 2 + VGAP + VIA_D / 2)
// reference keep-out: a slow trace on the ground layer stays this far (centre to centre) from a fast trace above/below
// it: the fast trace's half width + 3x the 0.076 mm prepreg + the slow trace's half width + clearance
const R_REF = W_SIG / 2 + 3 * 0.0764 + W_SIG / 2 + GAP, D_REF = disk(R_REF)
const D_EXW = disk((W_PWR - W_SIG) / 2 + P / 2), D_EXB = disk((W_BIG - W_SIG) / 2 + P / 2)
function stampDisk(arr: Uint16Array, c: number, offs: number[], s: number) {
  const i = c % NX, j = (c / NX) | 0
  for (let k = 0; k < offs.length; k += 2) { const ii = i + offs[k], jj = j + offs[k + 1]; if (ii >= 0 && jj >= 0 && ii < NX && jj < NY) arr[jj * NX + ii] += s }
}
function stampNet(n: Net, s: 1 | -1) {
  if (!n.path) return
  const DT = n.w > W_PWR ? D_TTB : n.w > W_SIG ? D_TTW : D_TT, DTV = n.w > W_PWR ? D_BTV : n.w > W_SIG ? D_WTV : D_TV
  const ref = GND_SIG && n.fast
  for (const p of n.path) for (let k = 0; k < p.length; k++) {
    const id = p[k], l = (id / NN) | 0, c = id - l * NN
    // inside a neck zone a wide trace is drawn at signal width (geometry()), so it keeps signal-width clearance there
    if (neck[c]) { stampDisk(occT[l], c, D_TT, s); stampDisk(occV, c, D_TV, s) } else { stampDisk(occT[l], c, DT, s); stampDisk(occV, c, DTV, s) }
    if (ref && (l === 0 || l === 2)) stampDisk(occT[l === 0 ? 4 : 5], c, D_REF, s)
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
const PAIR_PITCH = 0.28, attract = ALL_L.map(() => new Uint8Array(NN)), attractV = new Uint8Array(NN)
const ring = (r0: number, r1: number) => { const o: number[] = []; const k = Math.ceil(r1 / P); for (let dj = -k; dj <= k; dj++) for (let di = -k; di <= k; di++) { const d = Math.hypot(di, dj) * P; if (d >= r0 && d <= r1) o.push(di, dj) } return o }
const RING_T = ring(PAIR_PITCH - 0.06, PAIR_PITCH + 0.06), RING_V = ring(0.36, 0.55)
// where the follower may place a via under PAIR_VIA: beside a lead via, up to one BGA ball pitch (0.65 / 0.8 mm) away
const RING_PV = ring(0.3, 0.95), pairViaOK = new Uint8Array(NN)
let attractOn = false
// pair coupling: the follower may only use cells within FOLLOW_R of the lead's path (same layer; around the lead's
// vias on every layer) or within FOLLOW_T of its own terminals. A follower that cannot fit there routes freely but
// counts as DECOUPLE conflicts, and the lead's path gets history cost, until the pair fits together.
const followM = ALL_L.map(() => new Uint8Array(NN)), followMarked: number[] = []
// differential pairs only escape a BGA / fine-pitch field near their own balls/pins (PAIR_ESC mm); they never run
// across a field (under the BGA the channels between via rows hold one trace, so the two wires would split up)
const ownZone = new Uint8Array(NN), ownMarked: number[] = []
const D_ESC = disk(+(process.env.PAIR_ESC ?? 3.0))
let pairNet = false
function setOwn(n: Net | null) {
  for (const c of ownMarked) ownZone[c] = 0; ownMarked.length = 0; pairNet = false
  if (!n || !(n.partner || n.follows) || process.env.PAIR_ESC === "off") return
  for (const t of [...n.terms, ...n.drops]) for (const id of t.nodes) { const c = id % NN, i = c % NX, j = (c / NX) | 0
    for (let k = 0; k < D_ESC.length; k += 2) { const ii = i + D_ESC[k], jj = j + D_ESC[k + 1]; if (ii >= 0 && jj >= 0 && ii < NX && jj < NY) { const cc = jj * NX + ii; if (!ownZone[cc]) { ownZone[cc] = 1; ownMarked.push(cc) } } } }
  pairNet = true
}
// the lead's own keep-out, hard for its follower (per layer for traces, and for via sites)
const leadKO = ALL_L.map(() => new Uint8Array(NN)), leadKOV = new Uint8Array(NN), koMarked: number[] = []
let followOn = false
let D_FOL = disk(+(process.env.FOLLOW_R ?? 0.6)), D_FOLT = disk(+(process.env.FOLLOW_T ?? 2.0)), DECOUPLE = 25
const NECK_FREE = process.env.NECK_FREE === "1", PAIR_VIA = process.env.PAIR_VIA !== "0"  // default on: P and N always share vias
function setFollow(lead: Net, f: Net, on: boolean) {
  if (!on) {
    for (const id of followMarked) followM[(id / NN) | 0][id % NN] = 0; followMarked.length = 0
    for (const id of koMarked) { if (id < 0) leadKOV[-id - 1] = 0; else leadKO[(id / NN) | 0][id % NN] = 0 } koMarked.length = 0
    followOn = false; return
  }
  if (!lead.path) { followOn = false; return }
  const mark = (l: number, c: number, offs: number[]) => { const i = c % NX, j = (c / NX) | 0
    for (let k = 0; k < offs.length; k += 2) { const ii = i + offs[k], jj = j + offs[k + 1]; if (ii >= 0 && jj >= 0 && ii < NX && jj < NY) { const cc = jj * NX + ii; if (!followM[l][cc]) { followM[l][cc] = 1; followMarked.push(l * NN + cc) } } } }
  for (const p of lead.path) for (const id of p) mark((id / NN) | 0, id % NN, D_FOL)
  for (const c of lead.vias ?? []) for (let l = 0; l < NL; l++) mark(l, c, D_FOL)
  for (const t of [...f.terms, ...f.drops]) for (const id of t.nodes) for (let l = 0; l < NL; l++) mark(l, id % NN, D_FOLT)
  const ko = (l: number, c: number, offs: number[]) => { const i = c % NX, j = (c / NX) | 0
    for (let k = 0; k < offs.length; k += 2) { const ii = i + offs[k], jj = j + offs[k + 1]; if (ii >= 0 && jj >= 0 && ii < NX && jj < NY) { const cc = jj * NX + ii
      if (l < 0) { if (!leadKOV[cc]) { leadKOV[cc] = 1; koMarked.push(-cc - 1) } } else if (!leadKO[l][cc]) { leadKO[l][cc] = 1; koMarked.push(l * NN + cc) } } } }
  for (const p of lead.path) for (const id of p) { const l = (id / NN) | 0, c = id % NN; ko(l, c, D_TT); ko(-1, c, D_TV) }
  for (const c of lead.vias ?? []) { for (let l = 0; l < NL; l++) ko(l, c, D_TV); ko(-1, c, D_VV) }
  followOn = true
}
function setAttract(lead: Net | undefined, on: boolean) {
  if (!lead?.path) { attractOn = false; return }
  const v = on ? 1 : 0
  for (const p of lead.path) for (const id of p) { const l = (id / NN) | 0, c = id - l * NN, i = c % NX, j = (c / NX) | 0
    for (let k = 0; k < RING_T.length; k += 2) { const ii = i + RING_T[k], jj = j + RING_T[k + 1]; if (ii >= 0 && jj >= 0 && ii < NX && jj < NY) attract[l][jj * NX + ii] = v } }
  for (const c of lead.vias ?? []) { const i = c % NX, j = (c / NX) | 0
    for (let k = 0; k < RING_V.length; k += 2) { const ii = i + RING_V[k], jj = j + RING_V[k + 1]; if (ii >= 0 && jj >= 0 && ii < NX && jj < NY) attractV[jj * NX + ii] = v }
    for (let k = 0; k < RING_PV.length; k += 2) { const ii = i + RING_PV[k], jj = j + RING_PV[k + 1]; if (ii >= 0 && jj >= 0 && ii < NX && jj < NY) pairViaOK[jj * NX + ii] = v } }
  if (on) {
    // never attract the follower into the lead's own clearance: no follower via within via-to-trace distance of the
    // lead's path, no follower trace within trace-to-via distance of the lead's vias
    const clr = (arr: Uint8Array, c: number, offs: number[]) => { const i = c % NX, j = (c / NX) | 0
      for (let k = 0; k < offs.length; k += 2) { const ii = i + offs[k], jj = j + offs[k + 1]; if (ii >= 0 && jj >= 0 && ii < NX && jj < NY) arr[jj * NX + ii] = 0 } }
    for (const p of lead.path) for (const id of p) clr(attractV, id % NN, D_TV)
    for (const c of lead.vias ?? []) for (let l = 0; l < NL; l++) clr(attract[l], c, D_TV)
  }
  attractOn = on
}
const VIA_COST = 10, DIAG = Math.SQRT2, HW = +(process.env.HW ?? 1.3) // heuristic weight: > 1 trades a little path length for a much smaller search
const GND_COST = +(process.env.GND_COST ?? 4) // a ground-layer crossing costs this much more than a signal layer
let pres = 0.5, hard = false // hard: other nets' copper is an obstacle, not a price (endgame)
let local = false // endgame: priced fallback searches start near the net too (then widen to the whole board)
const isGoal = new Uint32Array(NL * NN)
let goalStamp = 1
/** cheapest path from any source node to any goal node (or, with goalVia, to any cell that can take a via) */
// Strict (endgame) searches look inside the terminals' bounding box grown by BOX mm, then a box twice as large: a
// net re-placed around a conflict stays near it, and a search that cannot succeed fails after a small area instead
// of the whole grid.
let bx0 = 0, bx1 = 0, by0 = 0, by1 = 0
function search(n: Net, sources: number[], goals: Int32Array | null, gx0: number, gy0: number, goalVia: boolean): number[] | null {
  let i0 = 1e9, i1 = -1e9, j0 = 1e9, j1 = -1e9
  const add = (id: number) => { const c = id % NN, i = c % NX, j = (c / NX) | 0; if (i < i0) i0 = i; if (i > i1) i1 = i; if (j < j0) j0 = j; if (j > j1) j1 = j }
  for (const s of sources) add(s)
  if (goals) for (const g of goals) add(g); else add(gy(gy0) * NX + gx(gx0))
  const M = Math.round(+(process.env.BOX ?? 3) / P)
  // priced (negotiation) searches keep the whole board, so a net can still take a long detour around congestion
  for (const m of hard ? [M, 2 * M] : local ? [M, 2 * M, 1e6] : [1e6]) {
    bx0 = Math.max(0, i0 - m); bx1 = Math.min(NX - 1, i1 + m); by0 = Math.max(0, j0 - m); by1 = Math.min(NY - 1, j1 + m)
    const p = searchIn(n, sources, goals, gx0, gy0, goalVia)
    if (p) return p
    if (bx0 === 0 && by0 === 0 && bx1 === NX - 1 && by1 === NY - 1) break
  }
  return null
}
function searchIn(n: Net, sources: number[], goals: Int32Array | null, gx0: number, gy0: number, goalVia: boolean): number[] | null {
  stamp++; goalStamp++
  heapK.length = 0; heapV.length = 0
  if (goals) for (const g of goals) isGoal[g] = goalStamp
  const wide = n.w > W_SIG, bT = n.w > W_PWR ? blockTB : wide ? blockTW : blockT, leadPair = !!n.partner
  // other nets' keep-outs in occT are sized for a 0.1 mm trace; a wider trace must also keep its extra half-width
  // clear of them, or it lands inside a thin neighbour's clearance (hard mode treats that as an obstacle)
  const extra = wide ? (n.w > W_PWR ? D_EXB : D_EXW) : null
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
    if ((l === 3 && !n.inner2) || (l >= 4 && !n.gnd)) continue
    for (let d = 0; d < 8; d++) {
      const di = d < 4 ? [1, -1, 0, 0][d] : [1, 1, -1, -1][d - 4], dj = d < 4 ? [0, 0, 1, -1][d] : [1, -1, 1, -1][d - 4]
      const ii = i + di, jj = j + dj
      if (ii < bx0 || jj < by0 || ii > bx1 || jj > by1) continue
      const cc = jj * NX + ii, nid = l * NN + cc
      if ((neck[cc] ? blockT : bT)[l][cc] && isGoal[nid] !== goalStamp) continue
      if (l === 3 && !corrOk(cc)) continue
      if (pairNet && neck[cc] && !ownZone[cc] && isGoal[nid] !== goalStamp) continue
      // the two wires may separate only near their own terminals (FOLLOW_T, to escape their balls); NECK_FREE=1 also frees
      // the whole BGA / fine-pitch zones (that let pairs wander apart for millimetres under the SoC)
      if (followOn && ((!followM[l][cc] && !(NECK_FREE && neck[cc])) || leadKO[l][cc]) && isGoal[nid] !== goalStamp) continue
      // a wide trace also needs its extra half width clear of other nets: an obstacle in strict mode, priced otherwise
      const wideHit = extra !== null && !clearWide(l, cc)
      if (hard && (occT[l][cc] || wideHit) && isGoal[nid] !== goalStamp) continue
      // the pair attraction discounts only the distance, never the price of another net's space
      // a pair's lead also pays for the room its follower needs beside it (the cheaper of the two sides, at the pair
      // pitch, perpendicular to the step); outside the BGA / fine-pitch zones, where the pads set the geometry anyway
      let room = 0
      if (leadPair && !neck[cc]) {
        const k = d < 4 ? 6 : 4, oi = -dj * k, oj = di * k
        const side = (si: number, sj: number) => { const ii = i + di + si, jj = j + dj + sj; if (ii < 0 || jj < 0 || ii >= NX || jj >= NY) return 3; const c2 = jj * NX + ii; return blockT[l][c2] ? 3 : occT[l][c2] }
        room = Math.min(side(oi, oj), side(-oi, -oj))
      }
      const cong = (1 + histT[l][cc]) * ((attractOn && attract[l][cc] ? 0.25 : 1) + pres * (occT[l][cc] + (wideHit ? 1 : 0) + room)) + (wide && occT[l][cc] ? 2 : 0) + (room >= 3 ? 2 : 0)
      const ng = g + (d < 4 ? 1 : DIAG) * cong * (l >= 4 ? GND_COST : 1)
      if (seen[nid] !== stamp || ng < gCost[nid]) { seen[nid] = stamp; gCost[nid] = ng; from[nid] = id; push(ng + h(cc), nid) }
    }
    if (!blockV[c] && corrOk(c)) for (let l2 = 0; l2 < NL; l2++) {
      if (l2 === l || (l2 === 3 && !n.inner2) || (l2 >= 4 && !n.gnd)) continue
      if (followOn && ((!followM[l2][c] && !(NECK_FREE && neck[c])) || leadKOV[c] || leadKO[l2][c])) continue
      // the follower changes layer only beside one of the lead's vias, so P and N get the same vias (PAIR_VIA=0: off)
      if (followOn && PAIR_VIA && !pairViaOK[c]) continue
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
  const lifted = n.partner?.path ? n.partner : null
  if (lifted) stampNet(lifted, -1)
  try { return routeNet1(n) } finally { if (lifted) stampNet(lifted, 1) }
}
function routeNet1(n: Net): boolean {
  if (n.follows) { setAttract(n.follows, true); setFollow(n.follows, n, true) }
  try {
    n.decoupled = false
    if (routeNet0(n)) return true
    // no path under the current prices: take the cheapest path ignoring other nets, so the net stays in the
    // negotiation as a conflict (and its neighbours learn to make room) instead of dropping out
    const keep = pres; pres = 0
    try {
      if (routeNet0(n)) return true
      if (!n.follows) return false
      // a follower that does not fit beside its lead: route it freely, counted as decoupled
      setFollow(n.follows, n, false); n.decoupled = true
      return routeNet0(n)
    } finally { pres = keep }
  } finally { if (n.follows) { setAttract(n.follows, false); setFollow(n.follows, n, false) } }
}
function routeNet0(n: Net): boolean {
  setOwn(n)
  try { return routeNet00(n) } finally { setOwn(null) }
}
function routeNet00(n: Net): boolean {
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
  if (n.decoupled) {
    k += DECOUPLE
    // push the lead away from where its follower cannot fit
    if (n.follows?.path) for (const p of n.follows.path) for (const id of p) histT[(id / NN) | 0][id % NN] += 0.2
  }
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
  // judged on the whole board: a fallback-routed net may push into nets outside the group
  const before = groupConflicts(nets)
  let bestT = Infinity, bestA = -1, best: Map<Net, { path: any; vias: any }> | null = null
  for (const n of group) stampNet(n, -1)
  const span = (n: Net) => { const ts = [...n.terms, ...n.drops]; const xs = ts.map((t) => t.x), ys = ts.map((t) => t.y); return Math.max(...xs) - Math.min(...xs) + Math.max(...ys) - Math.min(...ys) }
  // a big group gets fewer orders: every order re-routes all of its nets
  const T = group.length > 8 ? Math.min(tries, 6) : tries
  for (let a = 0; a < T; a++) {
    let order = a === 0 ? [...group].sort((x, y) => span(y) - span(x)) : [...group].sort(() => rand() - 0.5)
    // keep each pair's lead right before its follower
    order = order.filter((n) => !n.follows); for (const f of group.filter((n) => n.follows)) { const k = order.indexOf(f.follows!); order.splice(k < 0 ? order.length : k + 1, 0, f) }
    hard = true
    const placed: Net[] = []
    for (const n of order) {
      // no conflict-free path with everything else fixed: route it normally (priced), so the order still counts
      if (!routeNet0Hard(n)) { hard = false; local = true; routeNet(n); local = false; hard = true }
      stampNet(n, 1); placed.push(n)
    }
    hard = false
    const t = groupConflicts(nets)
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
    if (n.decoupled) k += DECOUPLE
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
    if (live.length && endgame(live, tries)) fixed++
  }
  console.log(`  endgame: ${fixed} of ${list.length} conflict clusters re-placed`)
  return fixed
}
function routeNet0Hard(n: Net): boolean {
  if (n.follows) { setAttract(n.follows, true); setFollow(n.follows, n, true) }
  try { n.decoupled = false; return routeNet0(n) } finally { if (n.follows) { setAttract(n.follows, false); setFollow(n.follows, n, false) } }
}
let failed: string[] = []
let dirty = nets
let best = Infinity, bestAt = 0
let bestSnap: Map<Net, { path: any; vias: any }> | null = null
// ---------------- polish: shorten the longer wire of a skewed pair on a finished routing ----------------
// POLISH=<routes.json>: load the routing, then for every pair whose P/N skew exceeds its limit re-route the longer
// member strictly (everything else fixed, conflict-free) inside a tight corridor along its partner; keep the new path
// only if it is shorter. Writes OUT routes/copper like a normal run.
let polishLoaded = false
if (process.env.POLISH) {
  const rj = await Bun.file(process.env.POLISH).json()
  for (const n of nets) {
    const r = rj.nets[n.name]; if (!r) continue
    const paths: Int32Array[] = []
    for (const sg of r.segs) {
      const l = L_OF[sg.layer]; if (l === undefined) continue
      const cells: number[] = []
      for (let k = 0; k < sg.pts.length; k++) {
        const i1 = gx(sg.pts[k].x), j1 = gy(sg.pts[k].y)
        if (k === 0) { cells.push(l * NN + j1 * NX + i1); continue }
        let i = gx(sg.pts[k - 1].x), j = gy(sg.pts[k - 1].y)
        while (i !== i1 || j !== j1) { i += Math.sign(i1 - i); j += Math.sign(j1 - j); cells.push(l * NN + j * NX + i) }
      }
      paths.push(Int32Array.from(cells))
    }
    n.path = paths; n.vias = r.vias.map((v: any) => gy(v.y) * NX + gx(v.x))
  }
  for (const n of nets) stampNet(n, 1)
  polishLoaded = true
  const lenOf = (n: Net) => { const g = geometry(n); return g.segs.reduce((s: number, sg: any) => s + sg.pts.slice(1).reduce((t: number, q: any, k: number) => t + Math.hypot(q.x - sg.pts[k].x, q.y - sg.pts[k].y), 0), 0) + 0.6 * g.vias.length }
  const LIM = (name: string) => (name.startsWith("USB") ? 0.25 : 0.13)
  const FR = disk(+(process.env.POLISH_R ?? 0.45))
  if (process.env.RENEG) {
    // continue the normal negotiation from this routing: only the over-skewed pairs are ripped up at first; their
    // neighbours join the negotiation as soon as they conflict
    const skewed = nets.filter((n) => n.partner && Math.abs(lenOf(n) - lenOf(n.partner!)) > Math.max(LIM(n.name), +(process.env.RENEG_MIN ?? 1.0)))
    dirty = skewed.flatMap((n) => [n, n.partner!])
    pres = +(process.env.PRESET ?? 2)
    console.log("renegotiate from the loaded routing; skewed pairs:", skewed.map((n) => n.name).join(","))
  }
  if (!process.env.RENEG) {
  for (const lead of nets.filter((n) => n.partner)) {
    const fol = lead.partner!
    const lp = lenOf(lead), lf = lenOf(fol)
    if (Math.abs(lp - lf) <= LIM(lead.name)) continue
    const longer = lp > lf ? lead : fol, other = longer === lead ? fol : lead
    const old = { path: longer.path, vias: longer.vias }, oldLen = Math.max(lp, lf)
    stampNet(longer, -1)
    // corridor along the other member (tighter than during negotiation), plus the longer member's own terminals
    const saveFol = D_FOL.slice(); D_FOL.length = 0; D_FOL.push(...FR)
    setFollow(other, longer, true); hard = true
    const ok = routeNet0(longer)
    hard = false; setFollow(other, longer, false); D_FOL.length = 0; D_FOL.push(...saveFol)
    const newLen = ok ? lenOf(longer) : Infinity
    if (ok && newLen < oldLen - 0.05) { stampNet(longer, 1); console.log(`polish ${longer.name}: ${oldLen.toFixed(2)} -> ${newLen.toFixed(2)} mm (partner ${Math.min(lp, lf).toFixed(2)})`) }
    else { longer.path = old.path; longer.vias = old.vias; stampNet(longer, 1); console.log(`polish ${longer.name}: no shorter clean path (${oldLen.toFixed(2)} mm, partner ${Math.min(lp, lf).toFixed(2)})`) }
  }
  // still skewed: re-route the whole pair strictly (lead with room for its follower, then the follower in a tight
  // corridor along it); keep it only if the skew improves and both fit cleanly
  for (const lead of nets.filter((n) => n.partner)) {
    const fol = lead.partner!
    const skew0 = Math.abs(lenOf(lead) - lenOf(fol))
    if (skew0 <= LIM(lead.name)) continue
    const old = [lead, fol].map((n) => ({ n, path: n.path, vias: n.vias }))
    stampNet(lead, -1); stampNet(fol, -1)
    hard = true
    let ok = routeNet0(lead)
    if (ok) {
      stampNet(lead, 1)
      const saveFol = D_FOL.slice(); D_FOL.length = 0; D_FOL.push(...FR)
      setFollow(lead, fol, true); ok = routeNet0(fol); setFollow(lead, fol, false)
      D_FOL.length = 0; D_FOL.push(...saveFol)
      stampNet(lead, -1)
    }
    hard = false
    const skew1 = ok ? Math.abs(lenOf(lead) - lenOf(fol)) : Infinity
    if (ok && skew1 < skew0 - 0.05) { stampNet(lead, 1); stampNet(fol, 1); console.log(`polish pair ${lead.name}: skew ${skew0.toFixed(2)} -> ${skew1.toFixed(2)} mm`) }
    else { for (const o of old) { o.n.path = o.path; o.n.vias = o.vias; stampNet(o.n, 1) } console.log(`polish pair ${lead.name}: no better clean pair route (skew ${skew0.toFixed(2)} mm)`) }
  }
  // still skewed: lift the pair and every net running near it, route the pair first (coupled, tight corridor), then
  // the neighbours strictly around it in several orders; keep it only if all fit and the skew improves
  const RN = Math.round(+(process.env.POLISH_NEAR ?? 0.8) / P)
  for (const lead of nets.filter((n) => n.partner)) {
    const fol = lead.partner!
    const skew0 = Math.abs(lenOf(lead) - lenOf(fol))
    if (skew0 <= LIM(lead.name)) continue
    const near = new Uint8Array(NN)
    for (const m of [lead, fol]) for (const p of m.path ?? []) for (const id of p) { const c = id % NN, i = c % NX, j = (c / NX) | 0
      for (let dj = -RN; dj <= RN; dj += 2) for (let di = -RN; di <= RN; di += 2) { const ii = i + di, jj = j + dj; if (ii >= 0 && jj >= 0 && ii < NX && jj < NY) near[jj * NX + ii] = 1 } }
    const others = nets.filter((n) => n !== lead && n !== fol && !n.plane && n.path?.some((p) => p.some((id) => near[id % NN])))
    // a neighbour pair moves as a pair
    for (const n of [...others]) { const q = n.partner ?? n.follows; if (q && q !== lead && q !== fol && !others.includes(q)) others.push(q) }
    const group = [lead, fol, ...others]
    const saved = group.map((n) => ({ n, path: n.path, vias: n.vias }))
    let best: { skew: number; st: { n: Net; path: any; vias: any }[] } | null = null
    for (let a = 0; a < +(process.env.POLISH_TRIES ?? 8); a++) {
      for (const n of group) stampNet(n, -1)
      const stamped: Net[] = []
      hard = true
      let ok = routeNet0(lead)
      if (ok) {
        stampNet(lead, 1); stamped.push(lead)
        const saveFol = D_FOL.slice(); D_FOL.length = 0; D_FOL.push(...FR)
        setFollow(lead, fol, true); ok = routeNet0(fol); setFollow(lead, fol, false)
        D_FOL.length = 0; D_FOL.push(...saveFol)
        if (ok) { stampNet(fol, 1); stamped.push(fol) }
      }
      let order = [...others].sort(() => rand() - 0.5)
      order = order.filter((n) => !n.follows); for (const f of others.filter((n) => n.follows)) { const k = order.indexOf(f.follows!); order.splice(k < 0 ? order.length : k + 1, 0, f) }
      if (ok) for (const n of order) { if (!routeNet0Hard(n)) { ok = false; break } stampNet(n, 1); stamped.push(n) }
      hard = false
      const skew1 = ok ? Math.abs(lenOf(lead) - lenOf(fol)) : Infinity
      if (ok && skew1 < skew0 - 0.05 && (!best || skew1 < best.skew)) best = { skew: skew1, st: group.map((n) => ({ n, path: n.path, vias: n.vias })) }
      // undo this try exactly, then put the saved routes back for the next one
      for (const n of stamped) stampNet(n, -1)
      for (const o of saved) { o.n.path = o.path; o.n.vias = o.vias }
      for (const n of group) stampNet(n, 1)
      if (best && best.skew <= LIM(lead.name)) break
    }
    if (best) {
      for (const n of group) stampNet(n, -1)
      for (const o of best.st) { o.n.path = o.path; o.n.vias = o.vias; stampNet(o.n, 1) }
      console.log(`polish area ${lead.name}: skew ${skew0.toFixed(2)} -> ${best.skew.toFixed(2)} mm (${others.length} neighbours re-placed)`)
    } else console.log(`polish area ${lead.name}: no clean improvement (skew ${skew0.toFixed(2)} mm, ${others.length} neighbours)`)
  }
  for (const n of nets) n.conflicts = conflictsOf(n)
  const OUTP = process.env.OUT ?? "_polish"
  await writeOut(dir + `/routes${OUTP}.json`, dir + `/copper${OUTP}.json`)
  console.log("polish done; conflicts", nets.reduce((s, n) => s + (n.conflicts ?? 0), 0))
  process.exit(0)
  }
}
for (let it = 0; it < MAXIT; it++) {
  failed = []
  for (const n of dirty) { stampNet(n, -1); if (!routeNet(n)) failed.push(n.name); stampNet(n, 1) }
  let total = 0; const bad: Net[] = []
  for (const n of nets) { n.conflicts = conflictsOf(n); if (n.conflicts) { total += n.conflicts; bad.push(n) } }
  console.log(`iter ${it} [${((performance.now() - t0) / 1e3).toFixed(0)}s] pres=${pres.toFixed(2)} conflicts=${total} nets=${bad.length} ${bad.slice(0, 8).map((n) => n.name).join(",")} failed=${failed.length} ${failed.slice(0, 6).join(",")}`)
  if (!total && !failed.length) break
  if (it % 10 === 9) await writeOut(dir + `/routes${process.env.OUT ?? ""}.ckpt.json`, dir + `/copper${process.env.OUT ?? ""}.ckpt.json`)
  if (total < best) {
    best = total; bestAt = it; bestSnap = new Map(nets.map((n) => [n, { path: n.path, vias: n.vias }]))
    if (it >= 8) await writeOut(dir + `/routes${process.env.OUT ?? ""}.best.json`, dir + `/copper${process.env.OUT ?? ""}.best.json`)
  }
  if (it - bestAt >= +(process.env.STALL ?? 4) && bestSnap) {
    // no progress for a while (or diverging): go back to the best routing seen, then re-place its conflict clusters
    if (total > best) {
      for (const n of nets) stampNet(n, -1)
      for (const n of nets) { const sv = bestSnap.get(n)!; n.path = sv.path; n.vias = sv.vias; stampNet(n, 1) }
      console.log(`  back to the best routing (pass ${bestAt}, ${best} conflicts)`)
    }
    // clean-up rounds while they keep lowering the board's total (each round re-clusters what is left)
    let prev = groupConflicts(nets)
    for (let r = 0; r < +(process.env.EG_ROUNDS ?? 6) && prev > 0; r++) {
      const snap = new Map(nets.map((n) => [n, { path: n.path, vias: n.vias }]))
      const b2: Net[] = []
      for (const n of nets) { n.conflicts = conflictsOf(n); if (n.conflicts) b2.push(n) }
      endgameClusters(b2, +(process.env.EG_TRIES ?? 24))
      const now = groupConflicts(nets)
      console.log(`  endgame round ${r}: ${prev} -> ${now}`)
      if (now >= prev) {
        // the round did not help: put the routing back as it was
        for (const n of nets) stampNet(n, -1)
        for (const n of nets) { const sv = snap.get(n)!; n.path = sv.path; n.vias = sv.vias; stampNet(n, 1) }
        break
      }
      prev = now
    }
    let t2 = 0; bad.length = 0
    for (const n of nets) { n.conflicts = conflictsOf(n); if (n.conflicts) { t2 += n.conflicts; bad.push(n) } }
    console.log(`  after endgame: conflicts=${t2}`)
    if (!t2 && !failed.length) break
    best = t2; bestAt = it; bestSnap = new Map(nets.map((n) => [n, { path: n.path, vias: n.vias }]))
    await writeOut(dir + `/routes${process.env.OUT ?? ""}.best.json`, dir + `/copper${process.env.OUT ?? ""}.best.json`)
    // negotiate on from the cleaned-up routing with a low present price (the learned history stays), so the next
    // pass refines it instead of scattering it
    pres = +(process.env.PRESET ?? 2)
    dirty = nets.filter((n) => n.conflicts)
    for (const n of [...dirty]) { if (n.partner && !dirty.includes(n.partner)) dirty.push(n.partner); if (n.follows && !dirty.includes(n.follows)) dirty.push(n.follows) }
    continue
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
// the result is the best routing seen, not whatever the last pass left
if (bestSnap) {
  let last = 0; for (const n of nets) last += n.conflicts ?? 0
  if (last > best) {
    for (const n of nets) stampNet(n, -1)
    for (const n of nets) { const sv = bestSnap.get(n)!; n.path = sv.path; n.vias = sv.vias; stampNet(n, 1) }
    for (const n of nets) n.conflicts = conflictsOf(n)
    console.log(`output: the best routing (pass ${bestAt}, ${best} conflicts) instead of the last pass (${last})`)
  }
}
const OUT = process.env.OUT ?? ""
await writeOut(dir + `/routes${OUT}.json`, dir + `/copper${OUT}.json`)
const ok = !failed.length && !nets.some((n) => n.conflicts)
console.log(ok ? "SOLVED" : `NOT SOLVED: failed ${failed.length}, in conflict ${nets.filter((n) => n.conflicts).length}`, `${((performance.now() - t0) / 1e3).toFixed(0)}s`)
