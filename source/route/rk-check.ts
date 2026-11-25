// Independent check of a routed RK3566 <-> LPDDR4 block: connectivity, copper DRC, Rockchip RK356x LPDDR4 rules
// (RK3568 High Speed PCB Design Guide, Table 33), spacing against 2W/3W. usage: bun rk-check.ts <routed.json> <input.json>
import { validateOriginalEndpointConnectivity, validateRoutedCopperDrc } from "/home/user/ts/fanout-solver/lib/index.ts"
const [routedPath, inputPath] = process.argv.slice(2)
const routed = await Bun.file(routedPath).json(), input = await Bun.file(inputPath).json()
const MIL = 0.0254, W = 0.11
const ddr = routed.traces.filter((t: any) => input.connections.some((c: any) => c.name === t.connection_name))
const byNet = new Map<string, any[]>(); for (const t of ddr) (byNet.get(t.connection_name) ?? byNet.set(t.connection_name, []).get(t.connection_name)!).push(t)
const len = (n: string) => (byNet.get(n) ?? []).reduce((s, t) => { let l = 0; const r = t.route; for (let i = 1; i < r.length; i++) if (r[i].route_type === "wire" && r[i - 1].route_type === "wire" && r[i].layer === r[i - 1].layer) l += Math.hypot(r[i].x - r[i - 1].x, r[i].y - r[i - 1].y); return s + l }, 0)
const vias = (n: string) => (byNet.get(n) ?? []).reduce((s, t) => s + t.route.filter((p: any) => p.route_type === "via").length, 0)
let ok = true
const line = (pass: boolean, msg: string) => { if (!pass) ok = false; console.log(`${pass ? "PASS" : "FAIL"}  ${msg}`) }
// connectivity + DRC (power fanout is supplied copper of other nets)
const supplied = [...new Set((input.traces ?? []).map((t: any) => t.connection_name))].map((name) => ({ name, pointsToConnect: [] }))
const conn: any = validateOriginalEndpointConnectivity({ inputSrj: input, routedSrj: routed } as any)
line(conn.issues.length === 0, `connectivity: ${conn.connectedConnectionCount}/${input.connections.length} connections, ${conn.issues.length} issues`)
const drc: any = validateRoutedCopperDrc({ inputSrj: { ...input, connections: [...input.connections, ...supplied] }, routedSrj: { ...routed, connections: [...input.connections, ...supplied] }, clearance: 0.1, allowBlindAndBuriedVias: false } as any)
line(drc.issues.length === 0, `copper DRC at 0.10 mm (JLCPCB 6-layer min 0.09): ${drc.issues.length} issues${drc.issues.length ? " e.g. " + JSON.stringify(drc.issues[0]).slice(0, 200) : ""}`)
// Rockchip Table 33
for (const ch of ["a", "b"]) {
  const ck = [`CK_t_${ch}`, `CK_c_${ch}`].map(len)
  line(Math.abs(ck[0] - ck[1]) <= 12 * MIL, `CK_${ch} P/N mismatch ${(Math.abs(ck[0] - ck[1]) / MIL).toFixed(1)} mil (< 12)`)
  const clk = (ck[0] + ck[1]) / 2
  const ca = [0, 1, 2, 3, 4, 5].map((i) => `CA${i}_${ch}`).concat([`CS0_${ch}`, `CKE0_${ch}`, `ODT_${ch}`])
  const worstCa = Math.max(...ca.map((n) => Math.abs(len(n) - clk)))
  line(worstCa <= 500 * MIL, `CA_${ch} to CLK worst mismatch ${(worstCa / MIL).toFixed(0)} mil (< 500)`)
  for (const b of [0, 1]) {
    const dqs = [`DQS${b}_t_${ch}`, `DQS${b}_c_${ch}`].map(len)
    line(Math.abs(dqs[0] - dqs[1]) <= 12 * MIL, `DQS${b}_${ch} P/N mismatch ${(Math.abs(dqs[0] - dqs[1]) / MIL).toFixed(1)} mil (< 12)`)
    const s = (dqs[0] + dqs[1]) / 2
    const dq = Array.from({ length: 8 }, (_, i) => `DQ${8 * b + i}_${ch}`).concat([`DMI${b}_${ch}`])
    const worst = Math.max(...dq.map((n) => Math.abs(len(n) - s)))
    line(worst <= 600 * MIL, `BYTE${b}_${ch} DQ/DM to DQS worst mismatch ${(worst / MIL).toFixed(0)} mil (< 600)`)
    line(Math.abs(s - clk) <= 1200 * MIL, `DQS${b}_${ch} to CLK_${ch} mismatch ${(Math.abs(s - clk) / MIL).toFixed(0)} mil (< 1200)`)
  }
}
// spacing: share of DDR copper whose nearest different-net DDR copper is closer than 2W (and 3W for CK/DQS)
type Seg = { a: any; b: any; layer: string; net: string }
const segs: Seg[] = []; for (const t of ddr) { const r = t.route; for (let i = 1; i < r.length; i++) if (r[i].route_type === "wire" && r[i - 1].route_type === "wire" && r[i].layer === r[i - 1].layer) segs.push({ a: r[i - 1], b: r[i], layer: r[i].layer, net: t.connection_name }) }
const segDist = (p: Seg, q: Seg) => { const pts = (s: Seg, k: number) => ({ x: s.a.x + (s.b.x - s.a.x) * k, y: s.a.y + (s.b.y - s.a.y) * k }); let m = Infinity; for (let i = 0; i <= 8; i++) for (const s of [q]) { const P = pts(p, i / 8), dx = s.b.x - s.a.x, dy = s.b.y - s.a.y, L = dx * dx + dy * dy, k = L ? Math.max(0, Math.min(1, ((P.x - s.a.x) * dx + (P.y - s.a.y) * dy) / L)) : 0; m = Math.min(m, Math.hypot(P.x - s.a.x - k * dx, P.y - s.a.y - k * dy)) } return m }
let tot = 0, below2 = 0, below3 = 0; const pairOf = (n: string) => n.replace(/_(t|c)_/, "_x_")
for (const p of segs) { const L = Math.hypot(p.b.x - p.a.x, p.b.y - p.a.y); tot += L; let m = Infinity
  for (const q of segs) if (q.net !== p.net && q.layer === p.layer && pairOf(q.net) !== pairOf(p.net)) m = Math.min(m, segDist(p, q))
  const edge = m - W; if (edge < 2 * W - 1e-6) below2 += L; if (/^(CK|DQS)/.test(p.net) && edge < 3 * W - 1e-6) below3 += L }
console.log(`INFO  spacing: ${(100 * below2 / tot).toFixed(1)}% of ${tot.toFixed(0)} mm DDR copper is closer than 2W (${(2 * W).toFixed(2)} mm edge) to another DDR net (BGA breakouts included); CK/DQS below 3W: ${below3.toFixed(1)} mm`)
const allV = [...byNet.keys()].map(vias); console.log(`INFO  vias per net: ${Math.min(...allV)}..${Math.max(...allV)}, total ${allV.reduce((a, b) => a + b, 0)}`)
console.log(ok ? "RESULT: PASS" : "RESULT: FAIL")
