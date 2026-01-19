###############################################################################
## Copyright (C) 2024 Analog Devices, Inc. All rights reserved.
### SPDX short identifier: ADIBSD
###############################################################################

package require qsys 14.0

source ../../scripts/adi_env.tcl
source $ad_hdl_dir/library/scripts/adi_ip_intel.tcl

ad_ip_create phase_meas {Phase Measurement System}

ad_ip_files phase_meas [list \
    phase_meas.v \
]

# Parameters
ad_ip_parameter SAMPLE_CLK_FREQ INTEGER 200000000 true [list \
    DISPLAY_NAME "Sample Clock Frequency (Hz)" \
]
ad_ip_parameter SAMPLE_INTERVAL_US INTEGER 500 true [list \
    DISPLAY_NAME "Sample Interval (microseconds)" \
]

# 200 MHz Sampling Clock
ad_interface clock sample_clk input 1

# Reset (active high)
ad_interface reset reset input 1 if_sample_clk

# Avalon-MM Clock (50 MHz sys_clk)
ad_interface clock avs_clk input 1

# Avalon-MM Reset
ad_interface reset avs_reset input 1 if_avs_clk

# Avalon-MM Slave Interface
add_interface avs avalon end
set_interface_property avs addressUnits WORDS
set_interface_property avs associatedClock avs_clk
set_interface_property avs associatedReset avs_reset
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
add_interface clk_a_in conduit end
set_interface_property clk_a_in associatedClock ""
set_interface_property clk_a_in associatedReset ""
add_interface_port clk_a_in clk_a_in clk_in Input 1

# Clock B input conduit
add_interface clk_b_in conduit end
set_interface_property clk_b_in associatedClock ""
set_interface_property clk_b_in associatedReset ""
add_interface_port clk_b_in clk_b_in clk_in Input 1

# Interrupt
add_interface irq interrupt end
set_interface_property irq associatedClock avs_clk
set_interface_property irq associatedReset avs_reset
add_interface_port irq irq irq Output 1
