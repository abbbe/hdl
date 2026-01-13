###############################################################################
## Copyright (C) 2023 Analog Devices, Inc. All rights reserved.
### SPDX short identifier: ADIBSD
###############################################################################

source $ad_hdl_dir/projects/scripts/adi_pd.tcl
source $ad_hdl_dir/projects/common/de10nano/de10nano_system_qsys.tcl


if [info exists ad_project_dir] {
  source ../../common/cn0579_qsys.tcl
} else {
  source ../common/cn0579_qsys.tcl
}

set_instance_parameter_value sys_spi {clockPolarity} {0}

#system ID
set_instance_parameter_value axi_sysid_0 {ROM_ADDR_BITS} {9}
set_instance_parameter_value rom_sys_0 {PATH_TO_FILE} "$mem_init_sys_file_path/mem_init_sys.txt"
set_instance_parameter_value rom_sys_0 {ROM_ADDR_BITS} {9}

sysid_gen_sys_init_file

# Pulse Counter for external 40MHz clock input
add_instance pulse_counter_0 pulse_counter
set_instance_parameter_value pulse_counter_0 {COUNTER_WIDTH} {32}

# Clock and reset connections
add_connection sys_clk.clk pulse_counter_0.clock
add_connection sys_clk.clk_reset pulse_counter_0.reset

# Export pulse input conduit
add_interface pulse_in conduit end
set_interface_property pulse_in EXPORT_OF pulse_counter_0.pulse_in

# CPU interconnect - map to address 0x00040000 (available address space)
ad_cpu_interconnect 0x00040000 pulse_counter_0.avs
