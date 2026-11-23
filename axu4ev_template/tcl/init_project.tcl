# Run in Vivado Tcl Console or batch mode:
#   vivado -mode batch -source tcl/init_project.tcl
#   vivado -mode batch -source tcl/init_project.tcl -tclargs generated/config.tcl
source [file join [file dirname [info script]] project_lib.tcl]
set config_dir ""
if {[info exists argv] && [llength $argv]} {
    if {[llength $argv] != 1} { error "Expected at most one config.tcl path or directory" }
    set config_dir [lindex $argv 0]
}
::axu4ev::initialize $config_dir
