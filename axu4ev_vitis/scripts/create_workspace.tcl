# Native XSCT (validated with 2023.1); arguments: exported hardware bundle, workspace directory.
if {[llength $argv] != 2} { error "Usage: create_workspace.tcl <export-dir> <workspace>" }
lassign $argv hw ws
set hw [file normalize $hw]
set ws [file normalize $ws]
set root [file normalize [file join [file dirname [info script]] ..]]
source [file join $hw config.tcl]
setws $ws
if {![file exists [file join $ws axu4ev_platform platform.spr]]} {
    platform create -name axu4ev_platform -hw [file join $hw axu4ev_system.xsa]
    domain create -name standalone_a53 -os standalone -proc psu_cortexa53_0
} else {
    platform active axu4ev_platform
    platform config -updatehw [file join $hw axu4ev_system.xsa]
}
domain active standalone_a53
bsp config stdin psu_uart_0
bsp config stdout psu_uart_0
platform write
platform generate
if {![file exists [file join $ws axu4ev_diagnostics .project]]} {
    app create -name axu4ev_diagnostics -platform axu4ev_platform -domain standalone_a53 -template {Empty Application(C)}
}
foreach source [glob [file join $root src *]] { file copy -force $source [file join $ws axu4ev_diagnostics src] }
file copy -force [file join $hw axu4ev_config.h] [file join $ws axu4ev_diagnostics src axu4ev_config.h]
app config -name axu4ev_diagnostics build-config debug
app config -name axu4ev_diagnostics linker-script [file join $ws axu4ev_diagnostics src lscript.ld]
app config -name axu4ev_diagnostics -add compiler-misc {-Wall -Wextra -Werror=implicit-function-declaration}
app build -name axu4ev_diagnostics
puts "AXU4EV_VITIS_BUILD_OK: [file join $ws axu4ev_diagnostics Debug axu4ev_diagnostics.elf]"
exit
