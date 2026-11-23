# Vivado project initialization from generated config.tcl. No Python dispatch.
namespace eval ::axu4ev {
    variable template_root [file normalize [file join [file dirname [info script]] ..]]
}
source [file join $::axu4ev::template_root tcl config_io.tcl]

proc ::axu4ev::initialize {{config_dir ""} {snapshot 1}} {
    variable template_root
    global cfg
    set root $template_root
    set current_ver [version -short]
    if {$current_ver ne "2023.1"} {
        if {[info exists ::env(ZYNQMP_STRICT_VERSION)] && $::env(ZYNQMP_STRICT_VERSION) eq "1"} {
            error "Validated toolchain is Vivado 2023.1 (running $current_ver with ZYNQMP_STRICT_VERSION=1)."
        }
        puts "WARNING: Validated toolchain is Vivado 2023.1; continuing with Vivado $current_ver."
    }
    if {$config_dir eq ""} { set config_dir [file join $root generated] }
    set config_dir [::axu4ev::load_configuration $config_dir $root]
    set id [string range $cfg(CONFIG_ID) 0 11]
    set out [file join $root build $id]
    set contract [file join $out contract]
    file mkdir $contract
    foreach name {config.json config.tcl axu4ev_config.h axu4ev-memory.dtsi} {
        set source [file normalize [file join $config_dir $name]]
        set target [file normalize [file join $contract $name]]
        if {$source ne $target} { file copy -force $source $target }
    }

    create_project -force axu4ev [file join $out project] -part $cfg(PART)
    set_property target_language Verilog [current_project]
    set_property simulator_language Mixed [current_project]
    source [file join $root board ps_config.tcl]
    source [file join $root tcl create_bd.tcl]
    set bd [get_files */axu4ev_system.bd]
    set_property SYNTH_CHECKPOINT_MODE None $bd
    generate_target all $bd
    set wrapper [make_wrapper -files $bd -top]
    add_files -norecurse $wrapper
    if {$cfg(PL_UART)} {
        add_files -fileset constrs_1 [file join $root constraints axu4ev_uart.xdc]
    }
    set_property top axu4ev_system_wrapper [current_fileset]
    update_compile_order -fileset sources_1

    set bd_snapshot [file join $root bd]
    if {!$snapshot} { set bd_snapshot [file join $out bd] }
    file mkdir $bd_snapshot
    file copy -force $bd [file join $bd_snapshot axu4ev_system.bd]
    file copy -force [lindex $wrapper 0] [file join $bd_snapshot axu4ev_system_wrapper.v]
    write_bd_tcl -force [file join $bd_snapshot axu4ev_system.tcl]
    write_hw_platform -fixed -force -file [file join $out axu4ev_pre_synth.xsa]
    puts "AXU4EV_PROJECT_OK: [file join $out project axu4ev.xpr]"
    return [list $root $out $contract]
}
