###############################################################################
## Copyright (C) 2024 Analog Devices, Inc. All rights reserved.
### SPDX short identifier: ADIBSD
###############################################################################

# System clock - 50 MHz
create_clock -period "20.000 ns" -name sys_clk [get_ports {sys_clk}]

# USB clock
create_clock -period "16.666 ns" -name usb1_clk [get_ports {usb1_clk}]

# Derive PLL clocks automatically
derive_pll_clocks
derive_clock_uncertainty

# PLL A and PLL B output clocks - treat as async to sys_clk and sampling clock
# These are dynamically reconfigurable so phase relationship is not known
# pixel_clk_pll.outclk0 (200 MHz) is used for sampling - async to measured clocks
set_clock_groups -asynchronous \
    -group [get_clocks {i_system_bd|pll_a|altera_pll_i|*}] \
    -group [get_clocks {i_system_bd|pll_b|altera_pll_i|*}] \
    -group [get_clocks {i_system_bd|pixel_clk_pll|altera_pll_i|*}] \
    -group [get_clocks {sys_clk}]

# PLL output clocks to GPIO pins - async outputs, relaxed constraints
set_false_path -to [get_ports {clk_a_out}]
set_false_path -to [get_ports {clk_b_out}]

# Phase measurement module - clock domain crossing constraints
# These are properly synchronized with 2-stage synchronizers or FIFOs
set_false_path -from [get_registers {*phase_meas*}] -to [get_registers {*phase_meas*sync*}]
set_false_path -from [get_registers {*phase_meas*fifo*}] -to [get_registers {*phase_meas*fifo*}]

# Edge counter inputs from clk_a/clk_b domains
set_false_path -from [get_registers {*phase_meas*rise*}]
set_false_path -from [get_registers {*phase_meas*fall*}]
set_false_path -from [get_registers {*phase_meas*edge*}]
set_false_path -from [get_registers {*phase_meas*cnt*}]
set_false_path -from [get_registers {*phase_meas*sample*}]

# Enable and control signals across domains
set_false_path -from [get_registers {*phase_meas*enable*}]
set_false_path -to [get_registers {*phase_meas*enable*}]
set_false_path -from [get_registers {*phase_meas*timestamp*}]
