###############################################################################
## Phase DPS Controller - Platform Designer Component
## SPDX-License-Identifier: MIT
###############################################################################

package require qsys 14.0

source ../../scripts/adi_env.tcl
source $ad_hdl_dir/library/scripts/adi_ip_intel.tcl

set_module_property NAME phase_dps_ctrl
set_module_property DESCRIPTION "PLL Dynamic Phase Shift Controller"
set_module_property VERSION 1.0
set_module_property GROUP "Phase Measurement"
set_module_property DISPLAY_NAME phase_dps_ctrl

# Source files
ad_ip_files phase_dps_ctrl [list \
    phase_dps_ctrl.v \
]

# Clock
ad_interface clock clk input 1

# Reset (active high, directly connected to clock)
ad_interface reset reset input 1 if_clk

# Avalon-MM Slave Interface (control from Linux)
add_interface avs avalon end
set_interface_property avs addressUnits WORDS
set_interface_property avs associatedClock if_clk
set_interface_property avs associatedReset if_reset
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

add_interface_port avs avs_address address Input 4
add_interface_port avs avs_read read Input 1
add_interface_port avs avs_readdata readdata Output 32
add_interface_port avs avs_write write Input 1
add_interface_port avs avs_writedata writedata Input 32

# Avalon-MM Master Interface (to PLL reconfig)
add_interface avm avalon start
set_interface_property avm addressUnits WORDS
set_interface_property avm associatedClock if_clk
set_interface_property avm associatedReset if_reset
set_interface_property avm bitsPerSymbol 8
set_interface_property avm burstOnBurstBoundariesOnly false
set_interface_property avm burstcountUnits WORDS
set_interface_property avm doStreamReads false
set_interface_property avm doStreamWrites false
set_interface_property avm holdTime 0
set_interface_property avm linewrapBursts false
set_interface_property avm maximumPendingReadTransactions 0
set_interface_property avm maximumPendingWriteTransactions 0
set_interface_property avm readLatency 0
set_interface_property avm readWaitTime 1
set_interface_property avm setupTime 0
set_interface_property avm timingUnits Cycles
set_interface_property avm writeWaitTime 0

add_interface_port avm avm_address address Output 6
add_interface_port avm avm_read read Output 1
add_interface_port avm avm_readdata readdata Input 32
add_interface_port avm avm_write write Output 1
add_interface_port avm avm_writedata writedata Output 32
add_interface_port avm avm_waitrequest waitrequest Input 1
