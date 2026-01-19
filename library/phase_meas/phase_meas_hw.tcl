###############################################################################
## Copyright (C) 2024 Analog Devices, Inc. All rights reserved.
### SPDX short identifier: ADIBSD
###############################################################################

package require qsys 14.0

source ../../scripts/adi_env.tcl
source $ad_hdl_dir/library/scripts/adi_ip_intel.tcl

set_module_property NAME phase_meas
set_module_property DESCRIPTION "Phase Measurement System"
set_module_property VERSION 1.0
set_module_property GROUP "Analog Devices"
set_module_property DISPLAY_NAME phase_meas

# Source files
ad_ip_files phase_meas [list \
    phase_meas.v \
]

# Parameters
add_parameter SAMPLE_CLK_FREQ INTEGER 200000000
set_parameter_property SAMPLE_CLK_FREQ DEFAULT_VALUE 200000000
set_parameter_property SAMPLE_CLK_FREQ DISPLAY_NAME "Sample Clock Frequency (Hz)"
set_parameter_property SAMPLE_CLK_FREQ HDL_PARAMETER true

add_parameter SAMPLE_INTERVAL_US INTEGER 500
set_parameter_property SAMPLE_INTERVAL_US DEFAULT_VALUE 500
set_parameter_property SAMPLE_INTERVAL_US DISPLAY_NAME "Sample Interval (microseconds)"
set_parameter_property SAMPLE_INTERVAL_US HDL_PARAMETER true

# 200 MHz Sampling Clock
ad_interface clock sample_clk input 1

# Reset (active high, directly connected to sample_clk)
ad_interface reset reset input 1 if_sample_clk

# Avalon-MM Clock (50 MHz sys_clk)
ad_interface clock avs_clk input 1

# Avalon-MM Reset
ad_interface reset avs_reset input 1 if_avs_clk

# Avalon-MM Slave Interface
add_interface avs avalon end
set_interface_property avs addressUnits WORDS
set_interface_property avs associatedClock if_avs_clk
set_interface_property avs associatedReset if_avs_reset
set_interface_property avs bitsPerSymbol 8
set_interface_property avs burstOnBurstBoundariesOnly false
set_interface_property avs burstcountUnits WORDS
set_interface_property avs explicitAddressSpan 0
set_interface_property avs holdTime 0
set_interface_property avs linewrapBursts false
set_interface_property avs maximumPendingReadTransactions 0
set_interface_property avs maximumPendingWriteTransactions 0
set_interface_property avs readLatency 0
set_interface_property avs readWaitTime 1
set_interface_property avs setupTime 0
set_interface_property avs timingUnits Cycles
set_interface_property avs writeWaitTime 0

add_interface_port avs avs_address address Input 5
add_interface_port avs avs_read read Input 1
add_interface_port avs avs_readdata readdata Output 32
add_interface_port avs avs_write write Input 1
add_interface_port avs avs_writedata writedata Input 32

# Clock A input conduit
ad_interface signal clk_a_in input 1 clk_in

# Clock B input conduit
ad_interface signal clk_b_in input 1 clk_in

# Interrupt
ad_interface intr irq output 1 if_avs_clk
