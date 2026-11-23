# Vivado initialization from saved config. No host-tool discovery or dispatch.
namespace eval ::fz5 {
    variable template_root [file normalize [file join [file dirname [info script]] ..]]
}
source [file join $::fz5::template_root tcl config_io.tcl]

proc ::fz5::initialize {{config_dir ""} {default_snapshot 1}} {
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
    set config_dir [::fz5::load_configuration $config_dir $root]
    set id [string range $cfg(CONFIG_ID) 0 11]
    set out [file join $root build $id]
    file mkdir $out
    set contract_dir [file join $out contract]
    file mkdir $contract_dir
    foreach n {config.json config.tcl fz5_config.h fz5-memory.dtsi} {
        set source_path [file normalize [file join $config_dir $n]]
        set target_path [file normalize [file join $contract_dir $n]]
        if {$source_path ne $target_path} { file copy -force $source_path $target_path }
    }
    create_project -force fz5 [file join $out project] -part $cfg(PART)
    set_property target_language Verilog [current_project]
    set_property simulator_language Mixed [current_project]
    source [file join $root board ps_config.tcl]
    source [file join $root tcl create_bd.tcl]
    set bd [get_files */fz5_system.bd]
    set_property SYNTH_CHECKPOINT_MODE None $bd
    generate_target all $bd
    set wrapper [make_wrapper -files $bd -top]
    add_files -norecurse $wrapper
    if {$cfg(PL_RS232)} { add_files -fileset constrs_1 [file join $root constraints fz5.xdc] }
    set_property top fz5_system_wrapper [current_fileset]
    update_compile_order -fileset sources_1
    set snapshot [file join $out bd]
    if {$default_snapshot} { set snapshot [file join $root bd] }
    file mkdir $snapshot
    file copy -force $bd [file join $snapshot fz5_system.bd]
    file copy -force [lindex $wrapper 0] [file join $snapshot fz5_system_wrapper.v]
    write_bd_tcl -force [file join $snapshot fz5_system.tcl]
    write_hw_platform -fixed -force -file [file join $out fz5_pre_synth.xsa]
    puts "FZ5_PROJECT_OK: $out/project/fz5.xpr"
    return [list $root $out $contract_dir]
}
