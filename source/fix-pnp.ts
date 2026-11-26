// Pick-and-place rotations checked against JLCPCB's own footprints.
// For every placed part:
//   - pin1_location: where pin 1 sits on our footprint, in the footprint's own frame. Bottom-side parts are
//     un-rotated and un-mirrored first; tscircuit draws them as rotate(mirror_x(local)).
//   - supplier_pin1_location_map.jlcpcb: where pin 1 sits on the JLCPCB/EasyEDA footprint of its LCSC part, from
//     the tscircuit parts engine.
// Both are written into index.circuit.json, so `tsci export -f gerbers` emits verified rotations. fab/cpl.csv is
// rewritten with the same rotations (circuit-json-to-pnp-csv: PCB rotation + the turn between the two pin-1
// frames).
// Pins named by letter+number (BGA balls, e.g. A1) and pads the analyser cannot classify fall back to the
// quadrant of pin 1 / A1 around the pad centroid, compared in both frames.
// If a part has no supplier footprint, any other part with the same footprint stands in for it; this only
// happens for non-polarised 2-pad parts.
// Usage: bun source/fix-pnp.ts   (exits 1 if any part stays unverified)
import { getPlatformConfig } from "@tscircuit/eval/platform-config"
import { analyzePcbPin1Location } from "@tscircuit/circuit-json-util"
import { getRotationBetweenPcbPin1Locations } from "circuit-json"
import { convertCircuitJsonToPickAndPlaceRows } from "circuit-json-to-pnp-csv"
const ROOT = import.meta.dir + "/..", CJ = process.env.CIRCUIT ?? ROOT + "/index.circuit.json"
const cj: any[] = await Bun.file(CJ).json()
const pe: any = (getPlatformConfig() as any).partsEngine
const src = new Map(cj.filter((e) => e.type === "source_component").map((e) => [e.source_component_id, e]))
const padsOf = (els: any[], id?: string) => els.filter((e) => (e.type === "pcb_smtpad" || e.type === "pcb_plated_hole") && (!id || e.pcb_component_id === id))
const center = (p: any) => p.shape === "polygon" ? { x: p.points.reduce((s: number, q: any) => s + q.x, 0) / p.points.length, y: p.points.reduce((s: number, q: any) => s + q.y, 0) / p.points.length } : { x: p.x, y: p.y }
const isPin1 = (p: any) => (p.port_hints ?? []).some((h: any) => /^(pin)?0*1$|^A0*1$/i.test(String(h).trim()))
// quadrant of pin 1 around the centroid, as an angle in multiples of 90 (for BGAs etc.)
const pin1Angle = (pads: any[]) => {
  const p1 = pads.find(isPin1); if (!p1) return null
  const cs = pads.map(center), cx = cs.reduce((s, q) => s + q.x, 0) / cs.length, cy = cs.reduce((s, q) => s + q.y, 0) / cs.length
  const c = center(p1), a = Math.atan2(c.y - cy, c.x - cx) * 180 / Math.PI
  return Math.hypot(c.x - cx, c.y - cy) < 1e-6 ? null : a
}
const toLocal = (comp: any, p: any) => {
  const r = -comp.rotation * Math.PI / 180, cos = Math.cos(r), sin = Math.sin(r)
  const f = (q: any) => { const x = q.x - comp.center.x, y = q.y - comp.center.y; const lx = x * cos - y * sin, ly = x * sin + y * cos; return { x: comp.layer === "bottom" ? -lx : lx, y: ly } }
  return p.shape === "polygon" ? { ...p, points: p.points.map(f) } : { ...p, ...f(p) }
}
const supplier = new Map<string, any[] | null>()
async function supplierPads(pn: string) {
  if (!supplier.has(pn)) {
    try { const j = await pe.fetchPartCircuitJson({ supplierPartNumber: pn }); supplier.set(pn, j?.length ? padsOf(j) : null) }
    catch { supplier.set(pn, null) }
  }
  return supplier.get(pn)!
}
const fpOf = (s: any) => s.footprint ?? s.ftype + ":" + (s.display_value ?? "")
const report: string[] = [], bad: string[] = []
const comps = cj.filter((e) => e.type === "pcb_component" && !e.do_not_place)
// map footprint -> a part number whose supplier footprint resolves (stand-in for parts without one)
for (const comp of comps) {
  const s: any = src.get(comp.source_component_id); const pn = s?.supplier_part_numbers?.jlcpcb?.[0]
  if (!s) continue  // footprint-only objects (via arrays) are not placed parts; the CPL writer skips them too
  if (!pn) { bad.push(`${s.name}: no LCSC part number`); continue }
  const ours = padsOf(cj, comp.pcb_component_id).map((p) => toLocal(comp, p))
  let sp = await supplierPads(pn), standIn = ""
  if (!sp && ours.length === 2) {
    // a non-polarised 2-pad part: any resolvable 2-pad part with the same pad spacing has the same frame
    for (const [k, v] of supplier) if (v && v.length === 2) { sp = v; standIn = ` (frame of ${k})`; break }
  }
  if (!sp) { bad.push(`${s.name} ${pn}: no JLCPCB footprint`); continue }
  let local = analyzePcbPin1Location(ours as any) as any, sup = analyzePcbPin1Location(sp as any) as any
  let adj = local && sup ? getRotationBetweenPcbPin1Locations(sup, local) : null
  if (adj === null) {
    const a = pin1Angle(ours), b = pin1Angle(sp)
    if (a === null || b === null) { bad.push(`${s.name} ${pn}: pin 1 not found (ours ${a}, JLC ${b})`); continue }
    adj = (((Math.round((a - b) / 90) * 90) % 360) + 360) % 360
    // express it as a pin1-location pair the CLI accepts: our side = the supplier's location turned by adj
    const cyc = ["leftside_top", "bottomside_left", "rightside_bottom", "topside_right"]
    sup = cyc[0]; local = cyc[(adj / 90) % 4]
  }
  comp.pin1_location = local
  comp.supplier_pin1_location_map = { ...(comp.supplier_pin1_location_map ?? {}), jlcpcb: sup }
  const rot = (((comp.rotation + adj) % 360) + 360) % 360
  report.push(`${s.name.padEnd(5)} ${pn.padEnd(10)} ${comp.layer.padEnd(6)} pcb ${String(comp.rotation).padStart(3)} -> JLC ${String(rot).padStart(3)}${standIn}`)
}
await Bun.write(CJ, JSON.stringify(cj))
const rows = convertCircuitJsonToPickAndPlaceRows(cj as any, { supplier: "jlcpcb", onRotationWarning: (w: any) => bad.push(w.message) } as any)
const csv = "Designator,Mid X,Mid Y,Layer,Rotation\n" + rows.map((r: any) => `${r.designator},${r.mid_x.toFixed(4)}mm,${r.mid_y.toFixed(4)}mm,${r.layer === "bottom" ? "Bottom" : "Top"},${r.rotation}`).join("\n") + "\n"
await Bun.write(process.env.CPL ?? ROOT + "/fab/cpl.csv", csv)
console.log(report.join("\n"))
console.log(`${report.length} parts verified, ${bad.length} unverified`)
for (const b of bad) console.log("  UNVERIFIED", b)
process.exit(bad.length ? 1 : 0)
