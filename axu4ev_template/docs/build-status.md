# Build Status

Last checked with Vivado 2023.1 on the AXU4EV-F template default profile.

## Completed Locally

- The hardware implementation used config ID `6a8d054f23be`. The current hardware-only config ID is `8900186fcb2c` after moving test options into the Vitis application.
- `config.json`, `config.tcl`, `axu4ev_config.h`, and `axu4ev-memory.dtsi` were generated.
- Vivado created `build/6a8d054f23be/project/axu4ev.xpr`.
- The block design passed `validate_bd_design`; generated wrapper, BD snapshot, and Tcl are under `bd/`.
- A pre-synthesis hardware platform was written to `build/6a8d054f23be/axu4ev_pre_synth.xsa`.
- Vivado 2023.1 synth, placement, physical optimization, routing, and bitstream generation completed successfully. Final routed DRC had 0 errors and 4 advisory warnings.
- Routed timing summary: WNS `5.915 ns`, TNS `0`, WHS `0.010 ns`, THS `0`; the router reported 0 unrouted nets.
- `build/6a8d054f23be/axu4ev_system.xsa` was exported with `-include_bit`. Zip integrity was checked and it contains `axu4ev_system.bit` (7,797,817 bytes).
- The Vitis handoff bundle is published in `export/` with the bitstream, XSA, JSON/Tcl/config header/memory fragment, and full config ID.
- The `minimal` profile uses an independent `.config`/output directory and passed Vivado BD validation and pre-synthesis XSA export as `build/5be3c4b73c70/axu4ev_pre_synth.xsa`. It does not run placement or routing.

## Hardware Verification Remaining

- No physical board was reset or programmed.
- Confirm physical carrier revision and SOM marking, then test UART, I2C, PHY/Ethernet link, QSPI/eMMC/SD, USB, DP, LEDs, PS DDR, and PL DMA on the target board.
- The companion Vitis workspace, diagnostic ELF and BOOT.BIN were generated from the final bit-enabled `export/axu4ev_system.xsa`. See [VALIDATION.md](VALIDATION.md) for software checks and artifact hashes; board tests remain pending.

The 4 final DRC advisories are Xilinx `RAMB18E2/RAMB36E2_nochange_collision_advisory`
warnings on the AXI DMA's internal FIFOs. The design passed implementation DRC.
BD validation also notes direct GPIO/PL-UART pin wiring and AXI `AWUSER`/`ARUSER`
width differences. The PS PMU reserves `0x7ff00000..0x7fffffff` (1 MiB) for
internal use; diagnostic software must avoid writing that region.
