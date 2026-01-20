###############################################################################
## Copyright (C) 2024 Analog Devices, Inc. All rights reserved.
### SPDX short identifier: ADIBSD
###############################################################################

set REQUIRED_QUARTUS_VERSION 24.1std.0
set QUARTUS_PRO_ISUSED 0
source ../../../scripts/adi_env.tcl
source ../../scripts/adi_project_intel.tcl

adi_project phase_meas_de10nano

source $ad_hdl_dir/projects/common/de10nano/de10nano_system_assign.tcl

# Downgrade Critical Warning related to an asynchronous RAM in the DMAC
# "mixed_port_feed_through_mode" parameter of RAM can not have value "old"
set_global_assignment -name MESSAGE_DISABLE 15003

# =============================================================================
# PLL Clock Outputs - Output 100 MHz clocks to GPIO for oscilloscope testing
# =============================================================================

# clk_a_out: GPIO_0[25] / PIN_W11 / JP1 pin 28
set_location_assignment PIN_W11 -to clk_a_out
set_instance_assignment -name IO_STANDARD "3.3-V LVTTL" -to clk_a_out
set_instance_assignment -name CURRENT_STRENGTH_NEW "MAXIMUM CURRENT" -to clk_a_out
set_instance_assignment -name SLEW_RATE 1 -to clk_a_out

# clk_b_out: GPIO_0[9] / PIN_AH3 / JP1 pin 14
set_location_assignment PIN_AH3 -to clk_b_out
set_instance_assignment -name IO_STANDARD "3.3-V LVTTL" -to clk_b_out
set_instance_assignment -name CURRENT_STRENGTH_NEW "MAXIMUM CURRENT" -to clk_b_out
set_instance_assignment -name SLEW_RATE 1 -to clk_b_out

# =============================================================================
# Build options
# =============================================================================

# Enable bitstream compression (required for FPGA manager loading)
set_global_assignment -name ON_CHIP_BITSTREAM_DECOMPRESSION ON

# Generate compressed RBF directly during compilation
set_global_assignment -name GENERATE_RBF_FILE ON

# =============================================================================
# SignalTap Debug - Observe clock signals
# =============================================================================

set_global_assignment -name ENABLE_SIGNALTAP ON
set_global_assignment -name USE_SIGNALTAP_FILE debug_clocks.stp
set_global_assignment -name SLD_NODE_CREATOR_ID 110 -section_id auto_signaltap_0
set_global_assignment -name SLD_NODE_ENTITY_NAME sld_signaltap -section_id auto_signaltap_0
set_instance_assignment -name POST_FIT_CONNECT_TO_SLD_NODE_ENTITY_PORT acq_clk -to "i_system_bd|sys_hps|fpga_interfaces|clocks_resets|h2f_user2_clk" -section_id auto_signaltap_0
set_global_assignment -name SLD_NODE_PARAMETER_ASSIGNMENT "SLD_RAM_BLOCK_TYPE=AUTO" -section_id auto_signaltap_0
set_global_assignment -name SLD_NODE_PARAMETER_ASSIGNMENT "SLD_DATA_BITS=10" -section_id auto_signaltap_0
set_global_assignment -name SLD_NODE_PARAMETER_ASSIGNMENT "SLD_TRIGGER_BITS=2" -section_id auto_signaltap_0
set_global_assignment -name SLD_NODE_PARAMETER_ASSIGNMENT "SLD_STORAGE_QUALIFIER_BITS=10" -section_id auto_signaltap_0
set_global_assignment -name SLD_NODE_PARAMETER_ASSIGNMENT "SLD_NODE_INFO=805334528" -section_id auto_signaltap_0
set_global_assignment -name SLD_NODE_PARAMETER_ASSIGNMENT "SLD_POWER_UP_TRIGGER=0" -section_id auto_signaltap_0
set_global_assignment -name SLD_NODE_PARAMETER_ASSIGNMENT "SLD_STORAGE_QUALIFIER_INVERSION_MASK_LENGTH=0" -section_id auto_signaltap_0
set_global_assignment -name SLD_NODE_PARAMETER_ASSIGNMENT "SLD_ATTRIBUTE_MEM_MODE=OFF" -section_id auto_signaltap_0
set_global_assignment -name SLD_NODE_PARAMETER_ASSIGNMENT "SLD_STATE_FLOW_USE_GENERATED=0" -section_id auto_signaltap_0
set_global_assignment -name SLD_NODE_PARAMETER_ASSIGNMENT "SLD_STATE_BITS=11" -section_id auto_signaltap_0
set_global_assignment -name SLD_NODE_PARAMETER_ASSIGNMENT "SLD_BUFFER_FULL_STOP=1" -section_id auto_signaltap_0
set_global_assignment -name SLD_NODE_PARAMETER_ASSIGNMENT "SLD_CURRENT_RESOURCE_WIDTH=1" -section_id auto_signaltap_0
set_global_assignment -name SLD_NODE_PARAMETER_ASSIGNMENT "SLD_SAMPLE_DEPTH=1024" -section_id auto_signaltap_0

# Preserve signals for SignalTap probing (prevent optimization)
set_instance_assignment -name PRESERVE_REGISTER ON -to "i_system_bd|phase_meas_0|clk_a_sync[*]"
set_instance_assignment -name PRESERVE_REGISTER ON -to "i_system_bd|phase_meas_0|clk_b_sync[*]"
set_instance_assignment -name PRESERVE_REGISTER ON -to "i_system_bd|phase_meas_0|clk_a_prev"
set_instance_assignment -name PRESERVE_REGISTER ON -to "i_system_bd|phase_meas_0|clk_b_prev"

execute_flow -compile
