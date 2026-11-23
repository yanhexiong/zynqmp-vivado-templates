# FZ5 V13 schematic sheet 11: PL_UART_RX=AE15, PL_UART_TX=AB14.
# They reach the RS232 transceiver on J12; never attach TTL UART wiring to J12.
# build.tcl loads this file only when CONFIG_PL_RS232=y. XDC contains static constraints.
set_property PACKAGE_PIN AE15 [get_ports rs232_rx]
set_property IOSTANDARD LVCMOS33 [get_ports rs232_rx]
set_property PULLUP true [get_ports rs232_rx]
set_property PACKAGE_PIN AB14 [get_ports rs232_tx]
set_property IOSTANDARD LVCMOS33 [get_ports rs232_tx]
set_property DRIVE 8 [get_ports rs232_tx]
set_property SLEW SLOW [get_ports rs232_tx]
# PS DDR, MIO and GTR use dedicated package pins configured in the PS IP.
# AXI clocks come from PS pl_clk0 and receive generated clock constraints from IP.
# Preserve normal UCIO/NSTD DRC severity; do not mask missing pin assignments.
