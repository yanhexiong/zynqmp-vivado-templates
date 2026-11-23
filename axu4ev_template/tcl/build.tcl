# Run a managed Vivado implementation and export the AXU4EV bitstream/XSA.
#   vivado -mode batch -source tcl/build.tcl -tclargs project|bitstream [config-dir]
set mode [lindex $argv 0]
if {$mode ni {project bitstream}} { error "Expected project or bitstream" }
if {[llength $argv] > 2} { error "Expected at most one configuration directory" }
set config_dir [lindex $argv 1]
source [file join [file dirname [info script]] project_lib.tcl]
lassign [::axu4ev::initialize $config_dir [expr {[llength $argv] == 1}]] root out contract
if {$mode eq "bitstream"} {
    launch_runs synth_1 -jobs 4
    wait_on_run synth_1
    launch_runs impl_1 -to_step write_bitstream -jobs 4
    wait_on_run impl_1
    set run_dir [get_property DIRECTORY [get_runs impl_1]]
    set run_bit [file join $run_dir axu4ev_system_wrapper.bit]
    if {![file isfile $run_bit]} { error "Implementation did not produce $run_bit" }
    set bit [file join $out axu4ev_system.bit]
    file copy -force $run_bit $bit
    set xsa [file join $out axu4ev_system.xsa]
    write_hw_platform -fixed -include_bit -force -file $xsa
    set publish [file join $root export]
    file mkdir $publish
    file copy -force $bit [file join $publish axu4ev_system.bit]
    file copy -force $xsa [file join $publish axu4ev_system.xsa]
    foreach name {config.json config.tcl axu4ev_config.h axu4ev-memory.dtsi} {
        file copy -force [file join $contract $name] [file join $publish $name]
    }
    set id_file [open [file join $publish config_id.txt] w]
    puts $id_file $cfg(CONFIG_ID)
    close $id_file
    puts "AXU4EV_BITSTREAM_OK: $bit"
    puts "AXU4EV_XSA_OK: $xsa"
    puts "AXU4EV_EXPORT_OK: $publish"
}
close_project
