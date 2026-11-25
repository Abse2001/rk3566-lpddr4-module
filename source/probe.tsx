// Renders one of every part at a known spot to record pad geometry (relative to the part origin) and courtyards.
// Output: source/design/footprints.json. Also checks how a bottom-side CM4 header lands.
import { Circuit } from "@tscircuit/core"
import { makePart } from "./parts"
import roles from "./design/roles.json"
const roleList = Object.keys(roles).filter((k) => !k.startsWith("_"))
const spots = roleList.map((r, i) => ({ role: r, x: (i % 8) * 25 - 90, y: Math.floor(i / 8) * 25 - 70 }))
const c = new Circuit()
c.add(<board width={260} height={200} layers={6} routingDisabled>
  {spots.map((s) => makePart({ ref: "P_" + s.role.replace(/[^A-Za-z0-9]/g, "_"), role: s.role, value: s.role.startsWith("C_") ? "100nF" : "1k" }, { x: s.x, y: s.y }))}
  {makePart({ ref: "JB", role: "DF40_HEADER", value: "" }, { x: 80, y: 80, layer: "bottom", oddSide: -1 })}
</board>)
await c.renderUntilSettled()
const cj: any[] = c.getCircuitJson()
const srcName = Object.fromEntries(cj.filter((e) => e.type === "source_component").map((e) => [e.source_component_id, e.name]))
const pcbComp = Object.fromEntries(cj.filter((e) => e.type === "pcb_component").map((e) => [e.pcb_component_id, e]))
const sport = Object.fromEntries(cj.filter((e) => e.type === "source_port").map((e) => [e.source_port_id, e]))
const pport = Object.fromEntries(cj.filter((e) => e.type === "pcb_port").map((e) => [e.pcb_port_id, e]))
const errs = cj.filter((e) => e.type.includes("error")); for (const e of errs.slice(0, 8)) console.log("ERR", e.type, (e.message ?? "").slice(0, 200)); console.log("names", Object.values(srcName).length)
const out: any = {}
for (const s of [...spots, { role: "DF40_HEADER_BOTTOM", x: 80, y: 80 }]) {
  const ref = s.role === "DF40_HEADER_BOTTOM" ? "JB" : "P_" + s.role.replace(/[^A-Za-z0-9]/g, "_")
  const comp = Object.values(pcbComp).find((p: any) => srcName[p.source_component_id] === ref) as any
  const pads = cj.filter((e) => e.type === "pcb_smtpad" && e.pcb_component_id === comp.pcb_component_id).map((p) => {
    const sp = sport[pport[p.pcb_port_id]?.source_port_id]
    return { names: [...new Set([sp?.name, ...(sp?.port_hints ?? [])].filter(Boolean))], x: +(p.x - s.x).toFixed(4), y: +(p.y - s.y).toFixed(4), w: p.width ?? p.radius * 2, h: p.height ?? p.radius * 2, shape: p.shape, layer: p.layer }
  })
  const xs = pads.flatMap((p) => [p.x - p.w / 2, p.x + p.w / 2]), ys = pads.flatMap((p) => [p.y - p.h / 2, p.y + p.h / 2])
  const cy = cj.filter((e) => e.type.includes("courtyard") && e.pcb_component_id === comp.pcb_component_id)
  const cpts = cy.flatMap((e: any) => e.outline ?? (e.center ? [{ x: e.center.x - e.width / 2, y: e.center.y - e.height / 2 }, { x: e.center.x + e.width / 2, y: e.center.y + e.height / 2 }] : []))
  const court = cpts.length ? [Math.min(...cpts.map((q: any) => q.x)) - s.x, Math.min(...cpts.map((q: any) => q.y)) - s.y, Math.max(...cpts.map((q: any) => q.x)) - s.x, Math.max(...cpts.map((q: any) => q.y)) - s.y] : null
  out[s.role] = { pads, padBox: [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)], court, comp: { w: comp.width, h: comp.height } }
}
await Bun.write(import.meta.dir + "/design/footprints.json", JSON.stringify(out))
for (const [k, v] of Object.entries(out) as any) console.log(k.padEnd(18), "pads", String(v.pads.length).padStart(3), "box", v.padBox.map((q: number) => q.toFixed(2)).join(","), "body", v.comp.w?.toFixed?.(2), v.comp.h?.toFixed?.(2))
const jb = out.DF40_HEADER_BOTTOM.pads, p1 = jb.find((p: any) => p.names.includes("1")), p2 = jb.find((p: any) => p.names.includes("2")), p99 = jb.find((p: any) => p.names.includes("99"))
console.log("bottom header: pin1", p1.x, p1.y, p1.layer, "pin2", p2.x, p2.y, "pin99", p99.x, p99.y)
