###############################################################################
## Copyright (C) 2024 Analog Devices, Inc. All rights reserved.
### SPDX short identifier: ADIBSD
###############################################################################

# Phase Measurement Test System for DE10-Nano
# Two PLLs with reconfiguration + 200MHz sampling clock + edge counters

source $ad_hdl_dir/projects/scripts/adi_pd.tcl

# Use full base system - minimal system broke HPS boot
# HDMI/video DMA uses resources but HPS bridge config is correct
source $ad_hdl_dir/projects/common/de10nano/de10nano_system_qsys.tcl

# System ID
set_instance_parameter_value axi_sysid_0 {ROM_ADDR_BITS} {9}
set_instance_parameter_value rom_sys_0 {PATH_TO_FILE} "$mem_init_sys_file_path/mem_init_sys.txt"
set_instance_parameter_value rom_sys_0 {ROM_ADDR_BITS} {9}

sysid_gen_sys_init_file

# =============================================================================
# PLL A - First clock output (100 MHz nominal, reconfigurable)
# =============================================================================

add_instance pll_a altera_pll
set_instance_parameter_value pll_a {gui_feedback_clock} {Global Clock}
set_instance_parameter_value pll_a {gui_operation_mode} {direct}
set_instance_parameter_value pll_a {gui_number_of_clocks} {1}
set_instance_parameter_value pll_a {gui_output_clock_frequency0} {100.0}
set_instance_parameter_value pll_a {gui_phase_shift0} {0}
set_instance_parameter_value pll_a {gui_phase_shift_deg0} {0.0}
set_instance_parameter_value pll_a {gui_pll_auto_reset} {Off}
set_instance_parameter_value pll_a {gui_pll_bandwidth_preset} {Auto}
set_instance_parameter_value pll_a {gui_pll_mode} {Fractional-N PLL}
set_instance_parameter_value pll_a {gui_ps_units0} {ps}
set_instance_parameter_value pll_a {gui_reference_clock_frequency} {50.0}
set_instance_parameter_value pll_a {gui_en_reconf} {1}

add_instance pll_a_reconfig altera_pll_reconfig
set_instance_parameter_value pll_a_reconfig {ENABLE_BYTEENABLE} {0}
set_instance_parameter_value pll_a_reconfig {ENABLE_MIF} {0}

add_connection pll_a.reconfig_from_pll pll_a_reconfig.reconfig_from_pll
add_connection pll_a.reconfig_to_pll pll_a_reconfig.reconfig_to_pll

add_connection sys_clk.clk pll_a.refclk
add_connection sys_clk.clk pll_a_reconfig.mgmt_clk
add_connection sys_clk.clk_reset pll_a.reset
add_connection sys_clk.clk_reset pll_a_reconfig.mgmt_reset

# Export PLL A clock output
add_interface pll_a_clk clock source
set_interface_property pll_a_clk EXPORT_OF pll_a.outclk0

# =============================================================================
# PLL B - Second clock output (100 MHz nominal, reconfigurable)
# =============================================================================

add_instance pll_b altera_pll
set_instance_parameter_value pll_b {gui_feedback_clock} {Global Clock}
set_instance_parameter_value pll_b {gui_operation_mode} {direct}
set_instance_parameter_value pll_b {gui_number_of_clocks} {1}
set_instance_parameter_value pll_b {gui_output_clock_frequency0} {100.0}
set_instance_parameter_value pll_b {gui_phase_shift0} {0}
set_instance_parameter_value pll_b {gui_phase_shift_deg0} {0.0}
set_instance_parameter_value pll_b {gui_pll_auto_reset} {Off}
set_instance_parameter_value pll_b {gui_pll_bandwidth_preset} {Auto}
set_instance_parameter_value pll_b {gui_pll_mode} {Fractional-N PLL}
set_instance_parameter_value pll_b {gui_ps_units0} {ps}
set_instance_parameter_value pll_b {gui_reference_clock_frequency} {50.0}
set_instance_parameter_value pll_b {gui_en_reconf} {1}

add_instance pll_b_reconfig altera_pll_reconfig
set_instance_parameter_value pll_b_reconfig {ENABLE_BYTEENABLE} {0}
set_instance_parameter_value pll_b_reconfig {ENABLE_MIF} {0}

add_connection pll_b.reconfig_from_pll pll_b_reconfig.reconfig_from_pll
add_connection pll_b.reconfig_to_pll pll_b_reconfig.reconfig_to_pll

add_connection sys_clk.clk pll_b.refclk
add_connection sys_clk.clk pll_b_reconfig.mgmt_clk
add_connection sys_clk.clk_reset pll_b.reset
add_connection sys_clk.clk_reset pll_b_reconfig.mgmt_reset

# Export PLL B clock output
add_interface pll_b_clk clock source
set_interface_property pll_b_clk EXPORT_OF pll_b.outclk0

# =============================================================================
# Phase DPS Controller - Controls PLL B dynamic phase shift
# Uses Avalon-MM master to write DPS registers and poll STATUS for completion
# =============================================================================

add_instance phase_dps_ctrl_0 phase_dps_ctrl

add_connection sys_clk.clk phase_dps_ctrl_0.if_clk
add_connection sys_clk.clk_reset phase_dps_ctrl_0.if_reset

# Connect DPS controller master to PLL B reconfig slave
add_connection phase_dps_ctrl_0.avm pll_b_reconfig.mgmt_avalon_slave

# =============================================================================
# Phase Measurement System
# TEST: Using sys_clk (50 MHz) as sample clock to verify system works
# Nyquist limit = 25 MHz, so can only measure clocks up to ~25 MHz
# =============================================================================

add_instance phase_meas_0 phase_meas
set_instance_parameter_value phase_meas_0 {SAMPLE_CLK_FREQ} {50000000}
set_instance_parameter_value phase_meas_0 {SAMPLE_INTERVAL_US} {500}

# TEST: Use sys_clk (50 MHz) for sampling to verify with known clock
add_connection sys_clk.clk phase_meas_0.if_sample_clk
add_connection sys_clk.clk_reset phase_meas_0.if_reset

# Connect 50 MHz sys_clk for register interface (if_avs_clk interface)
add_connection sys_clk.clk phase_meas_0.if_avs_clk
add_connection sys_clk.clk_reset phase_meas_0.if_avs_reset

# Export clock inputs (directly wired in system_top.v)
add_interface clk_a_in conduit end
set_interface_property clk_a_in EXPORT_OF phase_meas_0.if_clk_a_in

add_interface clk_b_in conduit end
set_interface_property clk_b_in EXPORT_OF phase_meas_0.if_clk_b_in

# =============================================================================
# CPU Interconnect - Memory mapped addresses
# =============================================================================

# PLL A reconfig: 0x00040000
ad_cpu_interconnect 0x00040000 pll_a_reconfig.mgmt_avalon_slave

# PLL B reconfig: 0x00041000
ad_cpu_interconnect 0x00041000 pll_b_reconfig.mgmt_avalon_slave

# Phase measurement registers: 0x00042000
ad_cpu_interconnect 0x00042000 phase_meas_0.avs

# Phase DPS controller registers: 0x00043000
ad_cpu_interconnect 0x00043000 phase_dps_ctrl_0.avs

# =============================================================================
# Interrupts
# =============================================================================

# Phase measurement interrupt on IRQ 4
ad_cpu_interrupt 4 phase_meas_0.interrupt_sender
