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

# PLL output clocks to GPIO pins - async outputs, relaxed constraints
set_false_path -to [get_ports {clk_a_out}]
set_false_path -to [get_ports {clk_b_out}]

# Clock domain crossing between sample_clk (200 MHz) and avs_clk (50 MHz)
# FIFO pointers and synchronizers handle the crossing
set_false_path -from [get_registers {*phase_meas*fifo_wr_ptr*}] -to [get_registers {*phase_meas*fifo_wr_ptr_sync1*}]
set_false_path -from [get_registers {*phase_meas*enable}] -to [get_registers {*phase_meas*enable_sync*}]
set_false_path -from [get_registers {*phase_meas*fifo_wr_en}] -to [get_registers {*phase_meas*fifo_wr_en_sync1*}]

# Raw counter synchronization
set_false_path -from [get_registers {*phase_meas*rise_cnt_a*}] -to [get_registers {*phase_meas*rise_cnt_a_sync*}]
set_false_path -from [get_registers {*phase_meas*fall_cnt_a*}] -to [get_registers {*phase_meas*fall_cnt_a_sync*}]
set_false_path -from [get_registers {*phase_meas*rise_cnt_b*}] -to [get_registers {*phase_meas*rise_cnt_b_sync*}]
set_false_path -from [get_registers {*phase_meas*fall_cnt_b*}] -to [get_registers {*phase_meas*fall_cnt_b_sync*}]
