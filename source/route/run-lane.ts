// RK3566 <-> LPDDR4 with NegotiatedLaneSolver: default stages, JLCPCB 6-layer 1080 rules.
// Prints each stage as it finishes and checkpoints finished stages, so a container restart resumes.
import { NegotiatedLaneSolver } from "/home/user/bus-lanes-solver/lib/negotiated-lane-solver.ts"
const D = "/tmp/claude-0/-home-user/b9d79f2d-030e-532c-84b5-c3a79e3230d3/scratchpad/rk/"
const TAG = process.env.TAG ?? "v3", CK = `${D}${TAG}.checkpoint.json`
const srj = await Bun.file(D + (process.env.IN ?? "v3.withpower.json")).json()
const solver: any = new NegotiatedLaneSolver(srj, { router: { w: 0.11, gap: 0.1, pairGap: 0.18, viaD: 0.25, viaHole: 0.15, allowViaInPad: process.env.VIP !== "0", verbose: !!process.env.VERB, ...(process.env.LAYERS ? { layers: process.env.LAYERS.split(",") } : {}) } })
if (await Bun.file(CK).exists()) {
  const c = await Bun.file(CK).json()
  solver.stages = c.stages; solver.stageIndex = c.stageIndex; solver.promotions = c.promotions; solver.log.push(...c.log)
  c.done.forEach((d: any, i: number) => (solver.done[i] = d))
  console.log(`resumed at stage ${c.stageIndex}`)
}
console.log("stages:", solver.stages.map((s: any) => s.connectionNames.length).join(","))
const t0 = performance.now(); let printed = solver.log.length, lastStage = solver.stageIndex
try {
  while (!solver.solved && !solver.failed) {
    solver.step()
    for (; printed < solver.log.length; printed++) console.log(`[${((performance.now() - t0) / 1e3).toFixed(0)}s]`, solver.log[printed])
    if (solver.stageIndex !== lastStage) {
      lastStage = solver.stageIndex
      await Bun.write(CK, JSON.stringify({ stages: solver.stages, stageIndex: solver.stageIndex, promotions: solver.promotions, done: solver.done, log: solver.log }))
    }
  }
} catch (e) { console.log("THREW", (e as Error).message) }
console.log("solved", solver.solved, "error", solver.error, ((performance.now() - t0) / 1e3).toFixed(0) + "s")
await Bun.write(D + `${TAG}.lane.routed.json`, JSON.stringify(solver.solved ? solver.getOutput() : { ...srj, traces: [...(srj.traces ?? []), ...solver.done.flat().filter(Boolean)] }))
