# AXU4EV-F Board Profile

## Device And Memory

The factory hardware handoff identifies `xczu4ev-sfvc784-2-i`. Evidence is in
the source bundle's `factory_file/axu4ev_f出厂vivado工程.zip`, under
`vivado/design_1_wrapper.xsa` and its `design_1.hwh` handoff. The factory
project was authored with Vivado 2020.1; this template rebuilds the design with
Vivado 2023.1.

The SOM schematic is
`hardware/01_SCH/M2CG_M3EG_M4EV_M5EV原理图.pdf` in the source bundle.
Its DDR4 wiring and the factory HWH describe one 64-bit PS DDR controller made
from x16, 8-Gbit devices. This is 4 GiB total PS DDR4. The SOM has no separate
PL DDR; PL masters reach shared DDR through `S_AXI_HP0_FPD`.

The physical memory and AXI decoder aperture are different quantities:

| Region | Start | Inclusive end | Size |
| --- | ---: | ---: | ---: |
| PS DDR low bank | `0x00000000` | `0x7fffffff` | 2 GiB |
| PS DDR high physical bank | `0x800000000` | `0x87fffffff` | 2 GiB |
| HP0 high DDR decode aperture | `0x800000000` | `0xfffffffff` | 32 GiB aperture |

The decoder aperture is not installed RAM. This leaves a hole between the low
and high banks for the PS peripheral and PCIe map. The default PL/DMA pool is
the top 1 GiB of the physical high bank, `0x840000000..0x87fffffff`; the PS
software memory contract reports 3 GiB available. The pool reservation is not
hardware isolation.

## PS And Carrier Peripherals

Factory settings and board connections were checked against the HWH and the
shared SOM schematic. Carrier documentation in this source bundle is titled
`AXU3EG-F-2025-12-17.pdf`, while the download directory and factory handoff are
AXU4EV-F. The SOM schematic covers several module variants. Confirm the carrier
revision and SOM marking on the physical specimen before using a generated
bitstream.

| Function | Verified mapping |
| --- | --- |
| PS UART0 | MIO42 RX, MIO43 TX; carrier CP2102 and USB connector J7; 115200 8N1 |
| Carrier PL UART | Separate CP2102/USB connector J8. On the tested board, RX is AH11 and TX is AH12 in bank 43 (LVCMOS33). |
| I2C0 | MIO34/35; carrier 24LC04 EEPROM U25 and LM75 sensor |
| EEPROM | 24LC04, A0/A1/A2 grounded; control blocks `0x50` and `0x51`, one-byte word offset |
| GEM3 | MIO64..75 plus MDIO MIO76/77; SOM RTL8211F, MDIO address 1 |
| Ethernet PHY reset | RTL8211F `RSTn` tied to active-low `PS_POR_B`, not a PS MIO GPIO |
| QSPI | MIO0..5 plus feedback clock MIO6; MT25QU256ABA 256 Mbit, JEDEC ID `20:BB:19` |
| eMMC | MTFC8GAKAJCN-4M, 8 GB; SD0 data/cmd/clock MIO13..22; `MMC_RSTN` on MIO23, active low |
| microSD | SD1 MIO46..51, card detect MIO45 |
| USB 2.0 | ULPI MIO52..63; reset_n MIO31; 26 MHz reference clock |
| USB 3.0 | PS GTR lane 1, Ref Clk1 at 26 MHz |
| DisplayPort | AUX MIO27..30, GTR lanes 3/2, Ref Clk2 at 27 MHz |
| PS LEDs | `PS_LED1` MIO39 and `PS_LED2` MIO40; active high through NPN low-side switches |

The carrier UART schematic shows two CP2102 chips and two independent USB
connectors, so PS console and PL UART can be opened at the same time.

## PL UART Pins

JTAG boundary scan on the tested board traced the J8 receive signal to `AH11`.
On that board, a direct echo from `AH11` to `AH12` returned all 24 test bytes
at 115200 8N1. The supplied carrier schematic and the factory Vivado project
give different UART pin pairs. The template uses the pinout verified on the
connected board, which also matches the UART table in the ALINX AXU4EV-E
manual. [ALINX AXU4EV-E user manual](https://alinx.com/public/upload/file/AXU4EV-E_User_Manual.pdf)

## Source Notes

- Factory XSA/HWH: `factory_file/axu4ev_f出厂vivado工程.zip`.
- SOM wiring: `hardware/01_SCH/M2CG_M3EG_M4EV_M5EV原理图.pdf`.
- Carrier wiring: `hardware/02_Carrier_board/底板原理图/AXU3EG-F-2025-12-17.pdf`.
- Package ball mapping: `hardware/SOMs_Pinlist.xlsx`.
- QSPI device datasheet: `hardware/03_chipset/QSPI FLASH/MT25QU256ABA.pdf`.
- EEPROM datasheet: Microchip 24LC04 family data sheet; the carrier wiring's grounded address pins select block addresses `0x50/0x51`.

The table reflects the schematics and factory handoff. On the board tested on
2026-11-20, MDIO address 1 returned JL2101 ID `937C:4032`. See the live checks
and the outstanding I2C0 result in [VALIDATION.md](VALIDATION.md).
