# Reusable configurable BD construction. cfg is loaded by build.tcl.
proc fz5_ip {name vlnv {props {}}} {
    set resolved $vlnv
    if {![llength [get_ipdefs -quiet $vlnv]]} {
        set base [join [lrange [split $vlnv :] 0 2] :]
        set candidates [lsort -dictionary [get_ipdefs -quiet "${base}:*"]]
        if {[llength $candidates]} {
            set resolved [lindex $candidates end]
            puts "WARNING: IP $vlnv unavailable in this Vivado version; using $resolved."
        }
    }
    set cell [create_bd_cell -type ip -vlnv $resolved $name]
    if {[llength $props]} { set_property -dict $props $cell }
    return $cell
}
proc fz5_net {args} {
    set pins {}
    foreach name $args { lappend pins [get_bd_pins $name] }
    connect_bd_net {*}$pins
}
proc fz5_axi {a b} { connect_bd_intf_net [get_bd_intf_pins $a] [get_bd_intf_pins $b] }

create_bd_design fz5_system
set ps [fz5_ip ps xilinx.com:ip:zynq_ultra_ps_e:3.5]
fz5_configure_ps $ps
set slaves {}
if {$cfg(PL_GPIO)} {
    fz5_ip gpio xilinx.com:ip:axi_gpio:2.0 [list CONFIG.C_IS_DUAL 1 CONFIG.C_GPIO_WIDTH 32 CONFIG.C_GPIO2_WIDTH 32 CONFIG.C_ALL_OUTPUTS 1 CONFIG.C_ALL_INPUTS_2 1]
    fz5_net gpio/gpio_io_o gpio/gpio2_io_i
    lappend slaves [list gpio/S_AXI $cfg(GPIO_BASE) gpio/S_AXI/Reg]
}
if {$cfg(PL_BRAM)} {
    fz5_ip bram_ctrl xilinx.com:ip:axi_bram_ctrl:4.1 [list CONFIG.DATA_WIDTH 32 CONFIG.SINGLE_PORT_BRAM 1 CONFIG.ECC_TYPE 0]
    fz5_ip bram xilinx.com:ip:blk_mem_gen:8.4 [list CONFIG.Memory_Type Single_Port_RAM CONFIG.use_bram_block BRAM_Controller]
    fz5_axi bram_ctrl/BRAM_PORTA bram/BRAM_PORTA
    lappend slaves [list bram_ctrl/S_AXI $cfg(BRAM_BASE) bram_ctrl/S_AXI/Mem0]
}
if {$cfg(PL_DMA)} {
    fz5_ip dma xilinx.com:ip:axi_dma:7.1 [list CONFIG.c_include_sg 0 CONFIG.c_addr_width 40 CONFIG.c_m_axi_mm2s_data_width 64 CONFIG.c_m_axi_s2mm_data_width 64 CONFIG.c_m_axis_mm2s_tdata_width 64 CONFIG.c_s_axis_s2mm_tdata_width 64 CONFIG.c_sg_length_width 23]
    fz5_ip stream_fifo xilinx.com:ip:axis_data_fifo:2.0 [list CONFIG.TDATA_NUM_BYTES 8 CONFIG.FIFO_DEPTH 1024 CONFIG.HAS_TLAST 1 CONFIG.HAS_TKEEP 1]
    fz5_axi dma/M_AXIS_MM2S stream_fifo/S_AXIS
    fz5_axi stream_fifo/M_AXIS dma/S_AXIS_S2MM
    fz5_ip ddr_interconnect xilinx.com:ip:smartconnect:1.0 [list CONFIG.NUM_SI 2 CONFIG.NUM_MI 1]
    fz5_axi dma/M_AXI_MM2S ddr_interconnect/S00_AXI
    fz5_axi dma/M_AXI_S2MM ddr_interconnect/S01_AXI
    fz5_axi ddr_interconnect/M00_AXI ps/S_AXI_HP0_FPD
    lappend slaves [list dma/S_AXI_LITE $cfg(DMA_BASE) dma/S_AXI_LITE/Reg]
}
if {$cfg(PL_RS232)} {
    fz5_ip rs232 xilinx.com:ip:axi_uartlite:2.0 [list CONFIG.C_BAUDRATE 115200 CONFIG.C_DATA_BITS 8 CONFIG.C_USE_PARITY 0]
    create_bd_port -dir I rs232_rx
    create_bd_port -dir O rs232_tx
    connect_bd_net [get_bd_ports rs232_rx] [get_bd_pins rs232/rx]
    connect_bd_net [get_bd_ports rs232_tx] [get_bd_pins rs232/tx]
    lappend slaves [list rs232/S_AXI $cfg(RS232_BASE) rs232/S_AXI/Reg]
}
if {[llength $slaves]} {
    # pl_resetn0 is active low; the unused auxiliary reset must be inactive at 0.
    fz5_ip reset xilinx.com:ip:proc_sys_reset:5.0 [list CONFIG.C_AUX_RESET_HIGH 1]
    fz5_ip const_one xilinx.com:ip:xlconstant:1.1 [list CONFIG.CONST_VAL 1]
    fz5_ip const_zero xilinx.com:ip:xlconstant:1.1 [list CONFIG.CONST_VAL 0]
    fz5_net ps/pl_clk0 reset/slowest_sync_clk ps/maxihpm0_fpd_aclk
    fz5_net ps/pl_resetn0 reset/ext_reset_in
    fz5_net const_one/dout reset/dcm_locked
    fz5_net const_zero/dout reset/aux_reset_in reset/mb_debug_sys_rst
    fz5_ip control_interconnect xilinx.com:ip:smartconnect:1.0 [list CONFIG.NUM_SI 1 CONFIG.NUM_MI [llength $slaves]]
    fz5_axi ps/M_AXI_HPM0_FPD control_interconnect/S00_AXI
    fz5_net ps/pl_clk0 control_interconnect/aclk
    fz5_net reset/interconnect_aresetn control_interconnect/aresetn
    set i 0
    foreach slave $slaves {
        lassign $slave intf base segment
        fz5_axi [format control_interconnect/M%02d_AXI $i] $intf
        create_bd_addr_seg -range 64K -offset $base [get_bd_addr_spaces ps/Data] [get_bd_addr_segs $segment] [format SEG_control_%d $i]
        incr i
    }
    foreach name {gpio bram_ctrl dma rs232} {
        if {![llength [get_bd_cells -quiet $name]]} { continue }
        foreach p [get_bd_pins -of_objects [get_bd_cells $name] -filter {TYPE == clk && DIR == I}] {
            connect_bd_net [get_bd_pins ps/pl_clk0] $p
        }
        foreach p [get_bd_pins -of_objects [get_bd_cells $name] -filter {TYPE == rst && DIR == I}] {
            connect_bd_net [get_bd_pins reset/peripheral_aresetn] $p
        }
    }
    if {$cfg(PL_DMA)} {
        fz5_net ps/pl_clk0 ps/saxihp0_fpd_aclk ddr_interconnect/aclk stream_fifo/s_axis_aclk
        fz5_net reset/peripheral_aresetn ddr_interconnect/aresetn stream_fifo/s_axis_aresetn
        # Assign both low/high DDR apertures, not the MMIO hole between them.
        assign_bd_address
    }
}
validate_bd_design
save_bd_design
