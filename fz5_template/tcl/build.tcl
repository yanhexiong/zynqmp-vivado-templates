# Optional full-build entry. Initialization is shared with init_project.tcl.
# vivado -mode batch -source tcl/build.tcl -tclargs project|bitstream [config-dir]
set mode [lindex $argv 0]
if {$mode ni {project bitstream}} { error "Expected project or bitstream" }
if {[llength $argv] > 2} { error "Expected at most one configuration directory" }
set config_dir [lindex $argv 1]
source [file join [file dirname [info script]] project_lib.tcl]
lassign [::fz5::initialize $config_dir [expr {[llength $argv] == 1}]] root out contract_dir
if {$mode eq "bitstream"} {
    synth_design -top fz5_system_wrapper -part $cfg(PART)
    opt_design
    place_design
    route_design
    source [file join $root tcl export_routed.tcl]
    fz5_export_routed $root $out $contract_dir
}
close_project
