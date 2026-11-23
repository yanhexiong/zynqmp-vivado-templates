# Windows/Linux, in Vivado Tcl Console:
#   source {/path/to/fz5_template/tcl/init_project.tcl}
# Or batch:
#   vivado -mode batch -source tcl/init_project.tcl
#   vivado -mode batch -source tcl/init_project.tcl -tclargs generated/config.tcl
# This entry only initializes the project, BD and handoff. It runs no Python.
source [file join [file dirname [info script]] project_lib.tcl]
set config_dir ""
if {[info exists argv] && [llength $argv]} {
    if {[llength $argv] != 1} { error "Expected at most one config.tcl path or configuration directory" }
    set config_dir [lindex $argv 0]
}
::fz5::initialize $config_dir
