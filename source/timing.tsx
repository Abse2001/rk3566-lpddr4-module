import { Circuit } from "@tscircuit/core"
import { makePart } from "./parts"
import netlist from "./design/netlist.json"
import placement from "./design/placement.json"
const sel = (process.env.SEL ?? "").split(",")
const comps = (netlist.components as any[]).filter((c) => sel.some((s) => s === "*" || c.ref.startsWith(s)))
const t0 = performance.now(), c = new Circuit()
c.add(<board width={40} height={55} layers={6} routingDisabled schAutoLayoutEnabled={false}><group pcbX={-16.5} pcbY={24}>{comps.map((x) => makePart(x, (placement as any)[x.ref]))}</group></board>)
await c.renderUntilSettled()
console.log(sel.join(","), comps.length, "parts", ((performance.now() - t0) / 1e3).toFixed(1) + "s")
