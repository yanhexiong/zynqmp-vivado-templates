# Pure Tcl configuration reader. It verifies that generated files match the .config.
namespace eval ::axu4ev {}

proc ::axu4ev::load_configuration {config_dir template_root} {
    global cfg
    if {[file isfile $config_dir]} { set config_dir [file dirname $config_dir] }
    set config_dir [file normalize $config_dir]
    set input [file join $config_dir config.tcl]
    if {![file isfile $input]} {
        error "Missing $input. Save configuration with: uv run axu4ev-config generate"
    }
    catch {unset cfg}
    source -encoding utf-8 $input
    if {![info exists axu4ev_config_format] || $axu4ev_config_format != 1 || ![array exists cfg]} {
        error "Unsupported configuration format. Run: uv run axu4ev-config generate"
    }
    foreach name {CONFIG_ID PART PL_CLOCK_MHZ PL_RESERVED_MB BOARD_AXU4EV PS_UART0 PS_I2C0} {
        if {![info exists cfg($name)]} { error "Configuration is missing $name" }
    }
    if {$axu4ev_config_source ne ""} {
        set source_path [file normalize [file join $template_root $axu4ev_config_source]]
        if {![file isfile $source_path]} { error "Configuration source is missing: $source_path" }
        set stream [open $source_path r]
        fconfigure $stream -encoding utf-8 -translation auto
        set current [string trimleft [read $stream] \ufeff]
        close $stream
        if {$current ne $axu4ev_config_source_text} {
            error "Configuration changed since config.tcl was saved. Run: uv run axu4ev-config generate"
        }
    }
    return $config_dir
}
