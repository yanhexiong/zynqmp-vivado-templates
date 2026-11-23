# Native XSCT. Caller verifies hashes and opens the UART capture before download.
if {[llength $argv] != 4} { error "Usage: run_jtag.tcl <export-dir> <workspace> <hw-server-url> <cable-pattern>" }
lassign $argv hw ws server cable
set xsa [file join $hw axu4ev_system.xsa]
set elf [file join [file dirname $ws] axu4ev_diagnostics.elf]
set bootdir [file join $ws axu4ev_platform export axu4ev_platform sw axu4ev_platform boot]
set fsbl [file join $bootdir fsbl.elf]
set pmufw [file join $bootdir pmufw.elf]
foreach path [list $fsbl $pmufw $elf] {
    if {![file isfile $path]} { error "Missing $path. Build the Vitis workspace first." }
}
source [file join $::env(XILINX_VITIS) scripts vitis util zynqmp_utils.tcl]
connect -url $server
set apu_filter "name =~ \"APU*\" && jtag_cable_name =~ \"$cable\""
set cpu_filter "name =~ \"*A53*#0\" && jtag_cable_name =~ \"$cable\""
set psu_filter "name == \"PSU\" && jtag_cable_name =~ \"$cable\""
set pmu_filter "name == \"MicroBlaze PMU\" && jtag_cable_name =~ \"$cable\""
# targets -set refuses ambiguous selections; never hard-code another board's cable serial.
targets -set -nocase -filter $apu_filter
rst -system
after 3000
targets -set -nocase -filter $psu_filter
# UG1137 JTAG boot sequence: expose the PMU target and run its RAM firmware before FSBL.
mwr -force 0xFFCA0038 0x1FF
after 500
targets -set -nocase -filter $pmu_filter
dow $pmufw
con
targets -set -nocase -filter $psu_filter
set pmu_ready 0
for {set i 0} {$i < 40} {incr i} {
    if {[mrd -force -value 0xFFD80000] & 0x10} {
        set pmu_ready 1
        break
    }
    after 50
}
if {!$pmu_ready} { error "PMU firmware did not start" }
puts "AXU4EV_JTAG_PMUFW_RUNNING"
fpga -file [file join $hw axu4ev_system.bit]
targets -set -nocase -filter $apu_filter
loadhw -hw $xsa -mem-ranges [list {0x80000000 0xbfffffff} {0x400000000 0x5ffffffff} {0x1000000000 0x7fffffffff}] -regs
configparams force-mem-access 1
targets -set -nocase -filter $cpu_filter
rst -processor
dow $fsbl
set bp [bpadd -addr &XFsbl_Exit]
con -block -timeout 90
bpremove $bp
if {!([mrd -force -value 0xFFCA3010] & 0x8)} { error "PL configuration did not assert DONE" }
targets -set -nocase -filter $cpu_filter
rst -processor
dow $elf
configparams force-mem-access 0
con
puts "AXU4EV_JTAG_RUNNING"
disconnect
exit
