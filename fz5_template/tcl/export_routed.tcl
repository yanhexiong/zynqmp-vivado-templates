# Called with an open, routed design. Shared by build.tcl and checkpoint recovery.
proc _fz5_find_python {root} {
    foreach var {FZ5_PYTHON ZYNQMP_PYTHON} {
        if {[info exists ::env($var)] && $::env($var) ne ""} {
            return $::env($var)
        }
    }
    foreach rel {{.venv bin python} {.venv Scripts python.exe}} {
        set cand [file join $root {*}$rel]
        if {[file isfile $cand]} { return $cand }
    }
    foreach cmd {python3 python} {
        set found [auto_execok $cmd]
        if {[llength $found]} { return [lindex $found 0] }
    }
    error "Python 3 interpreter not found. Set ::env(FZ5_PYTHON) or create .venv."
}

proc fz5_export_routed {root out config_dir} {
    report_timing_summary -file [file join $out timing_summary.rpt]
    report_utilization -file [file join $out utilization.rpt]
    report_drc -file [file join $out drc.rpt]
    set paths [get_timing_paths -quiet -max_paths 1 -setup]
    if {[llength $paths] && [get_property SLACK $paths] < 0} { error "Setup timing failed; see timing_summary.rpt" }
    set paths [get_timing_paths -quiet -max_paths 1 -hold]
    if {[llength $paths] && [get_property SLACK $paths] < 0} { error "Hold timing failed; see timing_summary.rpt" }
    write_checkpoint -force [file join $out fz5_routed.dcp]
    write_bitstream -force [file join $out fz5_system.bit]
    # -include_bit expects a managed implementation run. Keep the original
    # HWH/PS init content and add this flow's BIT with standard XSA descriptors.
    set python [_fz5_find_python $root]
    # Clear Vivado's embedded Python environment so host Python 3 does not load mismatched stdlib modules.
    set saved_env {}
    foreach var {PYTHONHOME PYTHONPATH} {
        if {[info exists ::env($var)]} {
            lappend saved_env $var $::env($var)
            unset ::env($var)
        }
    }
    set code [catch {
        exec $python [file join $root scripts package_xsa.py] \
            [file join $out fz5_pre_synth.xsa] [file join $out fz5_system.bit] \
            [file join $out fz5_system.xsa] --config-dir $config_dir --publish [file join $root export]
    } result options]
    foreach {var val} $saved_env {
        set ::env($var) $val
    }
    if {$code != 0} {
        return -options $options $result
    }
    puts $result
}
