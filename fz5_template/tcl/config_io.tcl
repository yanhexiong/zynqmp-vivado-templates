# Pure Tcl: load a saved configuration. Never invokes Python or a shell.
namespace eval ::fz5 {}

proc ::fz5::load_configuration {config_dir template_root} {
    global cfg
    if {[file isfile $config_dir]} { set config_dir [file dirname $config_dir] }
    set config_dir [file normalize $config_dir]
    set input [file join $config_dir config.tcl]
    if {![file isfile $input]} {
        error "Missing $input. Save configuration with: uv run python config.py"
    }
    catch {unset cfg}
    source -encoding utf-8 $input
    if {![info exists fz5_config_format] || $fz5_config_format != 1 || ![array exists cfg]} {
        error "Unsupported configuration format. Run: uv run python config.py generate"
    }
    foreach name {CONFIG_ID PART PL_CLOCK_MHZ PL_RESERVED_MB BOARD_FZ5D PS_UART0} {
        if {![info exists cfg($name)]} { error "Configuration is missing $name" }
    }
    if {$fz5_config_source ne ""} {
        set source_path [file normalize [file join $template_root $fz5_config_source]]
        if {![file isfile $source_path]} { error "Configuration source is missing: $source_path" }
        set stream [open $source_path r]
        fconfigure $stream -encoding utf-8 -translation auto
        set current [string trimleft [read $stream] \ufeff]
        close $stream
        if {$current ne $fz5_config_source_text} {
            error "Configuration changed since config.tcl was saved. Run: uv run python config.py generate"
        }
    }
    return $config_dir
}
