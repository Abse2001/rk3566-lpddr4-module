# ECO candidate (l11)

The published routing with only the changed nets re-routed:
- the JLCPCB-spacing placement,
- the delay-matched RAM block v22,
- the reserved CM4_ID_SD escape.

Then `finish_eco.sh`, PCIe TX re-routed (P/N 0.00 mm), the VDD_GPU inductor feed as a 0.3 mm stub into its
island, and the C86/C87 ground drops re-made.

Results:
- **check.py:** exit 0. 0 clearance, edge, hole, pad or reference-plane violations; 234/234 nets; every island
  one piece.
- **dfm_spacing.py:** 0 pairs below JLCPCB's SMD spacing table.
- **ddr_timing.py:** PASS. All RAM pairs 0.0–0.1 ps.
- **pairs.py:** 15/17. MIPI_DSI_TX1_D0 skew 2.31 mm and MIPI_DSI_TX1_D1 skew 1.51 mm are still over the
  0.13 mm limit. Both pairs leave the SoC's outer ball row where the strict re-route and the tuner find no room.
