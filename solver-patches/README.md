# Local solver changes

These patches against [tscircuit/bus-lanes-solver](https://github.com/tscircuit/bus-lanes-solver) are recorded here
because they are not yet in that repository. Base: branch `feat/negotiated-lane-solver` at `4cd438f`.

```bash
git -C bus-lanes-solver checkout -b feat/delay-aware-pair-matching 4cd438f
git -C bus-lanes-solver am ../rk3566-module/solver-patches/bus-lanes-solver/*.patch
```

What they change in the negotiated-lane DDR router:

1. **Delay-aware lengths.** `layerZ`, `layerDelay` and `viaDelayFactor` make pair trims and bus windows match
   in time. Each via counts its barrel and each layer its delay per mm. Without them, a pair whose rear member
   dives under its partner's ball matched in plane length while being 50–63 ps apart on the RK3566.
2. **Symmetric vias.** A pair whose members carry unequal via counts moves off its terminal layer, so each
   member changes layer once at each end.
3. **Tuned by the copper produced.** A pair counts as tuned only by the lengths its trims achieve. The log
   prints each pair's emitted skew next to the model's.
4. **Tuning zone.** Only package pads (`componentId`) bound the tuning zone, so reserved escape stubs of other
   CPU balls can be passed in as obstacles.

The RK3566 runner (`source/route/run-lane.ts`) passes the JLC06161H-1080A stackup:
`layerZ`, `layerDelay` (inner3 1.16) and `viaDelayFactor` 1.2.
