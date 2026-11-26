// Fabrication outputs from index.circuit.json, design/netlist.json, design/placement.json, design/roles.json:
// Gerbers + drills (circuit-json-to-gerber), BOM and pick-and-place in JLCPCB's CSV layout, CM4 pin map.
import { convertCircuitJsonToGerberFiles } from "circuit-json-to-gerber"
import { mkdirSync, rmSync } from "node:fs"
const S = import.meta.dir, OUT = process.env.FAB_OUT ?? S + "/../fab"
const cj = await Bun.file(process.env.CIRCUIT ?? S + "/../index.circuit.json").json()
const net = await Bun.file(S + "/design/netlist.json").json(), place = await Bun.file(S + "/design/placement.json").json()
const roles = await Bun.file(S + "/design/roles.json").json(), cm4 = await Bun.file(S + "/design/cm4-map.json").json()
rmSync(OUT + "/gerbers", { recursive: true, force: true }); mkdirSync(OUT + "/gerbers", { recursive: true })
const files = convertCircuitJsonToGerberFiles(cj)
for (const [name, text] of Object.entries(files)) await Bun.write(`${OUT}/gerbers/${name}`, text as string)
console.log("gerber files:", Object.entries(files).map(([n, t]) => `${n} (${((t as string).length / 1024).toFixed(0)}k)`).join(", "))
// board origin for the pick-and-place: the board centre, as in the gerbers
const CX = 16.5, CY = -24
const desc = (c: any) => {
  const r = roles[c.role]
  if (r.import) return r.import.replace(/_/g, "-")
  return `${c.value} ${r.fp}`
}
const pkg = (c: any) => roles[c.role].fp ?? roles[c.role].import
const groups = new Map<string, { comment: string; fp: string; lcsc: string; refs: string[] }>()
for (const c of net.components) {
  const r = roles[c.role], k = `${r.lcsc}|${desc(c)}`
  const g = groups.get(k) ?? { comment: desc(c), fp: pkg(c), lcsc: r.lcsc, refs: [] }
  g.refs.push(c.ref); groups.set(k, g)
}
await Bun.write(OUT + "/bom.csv", "Comment,Designator,Footprint,LCSC Part #\n" + [...groups.values()].map((g) => `"${g.comment}","${g.refs.join(",")}","${g.fp}",${g.lcsc}`).join("\n") + "\n")
await Bun.write(OUT + "/cpl.csv", "Designator,Mid X,Mid Y,Layer,Rotation\n" + net.components.map((c: any) => { const p = place[c.ref]
  return `${c.ref},${(p.x - CX).toFixed(4)}mm,${(p.y - CY).toFixed(4)}mm,${p.layer === "top" ? "Top" : "Bottom"},${(((p.rot ?? 0) % 360) + 360) % 360}` }).join("\n") + "\n")
await Bun.write(OUT + "/cm4-pinmap.csv", "CM4 pin,CM4 signal,Module net,RK3566 ball,Note\n" + Object.entries(cm4).map(([pin, v]: any) => `${pin},"${v.cm4}",${v.net ?? "NC"},${v.ball ?? ""},"${v.note ?? ""}"`).join("\n") + "\n")
const top = net.components.filter((c: any) => place[c.ref].layer === "top").length
console.log(`bom: ${groups.size} lines, ${net.components.length} parts (${top} top, ${net.components.length - top} bottom)`)
