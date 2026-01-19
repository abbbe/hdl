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

execute_flow -compile
