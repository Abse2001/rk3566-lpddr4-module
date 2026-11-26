Run 61 (GND_SIG, GND_SIG_BGA, INNER2_OPEN, GND_COST=2, SEED=5), best routing after 73 passes, plus repair.py.
check.py with planes.py on this copper: 0 clearance violations, 0 edge/hole, 0 via-hole, 0 pad-pad, 0 reference-plane
issues, 234/234 nets connected. Not final: after tune_pairs.py three pairs still exceed the P/N skew limit
(MIPI_CSI_RX_D2 3.7 mm, MIPI_DSI_TX1_CLK 4.2 mm, MIPI_DSI_TX1_D1 1.5 mm); the pairs wandered apart inside the SoC
ball field. Kept as a fallback while the tighter pair coupling is routed.
