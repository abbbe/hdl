# ***************************************************************************
# ***************************************************************************
# Pulse Counter - Qsys Component Definition
# ***************************************************************************
# ***************************************************************************

package require -exact qsys 14.0

# Module properties
set_module_property NAME pulse_counter
set_module_property DISPLAY_NAME "Pulse Counter"
set_module_property DESCRIPTION "Counts pulses from an external clock input"
set_module_property VERSION 1.0
set_module_property GROUP "Custom"
set_module_property AUTHOR "Custom"
set_module_property ELABORATION_CALLBACK elaborate

# File sets
add_fileset QUARTUS_SYNTH QUARTUS_SYNTH "" ""
set_fileset_property QUARTUS_SYNTH TOP_LEVEL pulse_counter
add_fileset_file pulse_counter.v VERILOG PATH pulse_counter.v TOP_LEVEL_FILE

add_fileset SIM_VERILOG SIM_VERILOG "" ""
set_fileset_property SIM_VERILOG TOP_LEVEL pulse_counter
add_fileset_file pulse_counter.v VERILOG PATH pulse_counter.v TOP_LEVEL_FILE

# Parameters
add_parameter COUNTER_WIDTH INTEGER 32
set_parameter_property COUNTER_WIDTH DEFAULT_VALUE 32
set_parameter_property COUNTER_WIDTH DISPLAY_NAME "Counter Width"
set_parameter_property COUNTER_WIDTH DESCRIPTION "Width of the pulse counter in bits"
set_parameter_property COUNTER_WIDTH ALLOWED_RANGES {16 32 64}
set_parameter_property COUNTER_WIDTH HDL_PARAMETER true

proc elaborate {} {
  # Clock interface
  add_interface clock clock end
  add_interface_port clock clk clk Input 1

  # Reset interface
  add_interface reset reset end
  set_interface_property reset associatedClock clock
  add_interface_port reset reset_n reset_n Input 1

  # Avalon-MM Slave interface
  add_interface avs avalon end
  set_interface_property avs addressUnits WORDS
  set_interface_property avs associatedClock clock
  set_interface_property avs associatedReset reset
  set_interface_property avs bitsPerSymbol 8
  set_interface_property avs burstOnBurstBoundariesOnly false
  set_interface_property avs burstcountUnits WORDS
  set_interface_property avs explicitAddressSpan 0
  set_interface_property avs holdTime 0
  set_interface_property avs linewrapBursts false
  set_interface_property avs maximumPendingReadTransactions 0
  set_interface_property avs readLatency 0
  set_interface_property avs readWaitTime 0
  set_interface_property avs setupTime 0
  set_interface_property avs timingUnits Cycles
  set_interface_property avs writeWaitTime 0

  add_interface_port avs avs_read read Input 1
  add_interface_port avs avs_write write Input 1
  add_interface_port avs avs_address address Input 2
  add_interface_port avs avs_writedata writedata Input 32
  add_interface_port avs avs_readdata readdata Output 32

  # External pulse input conduit
  add_interface pulse_in conduit end
  set_interface_property pulse_in associatedClock clock
  set_interface_property pulse_in associatedReset reset
  add_interface_port pulse_in pulse_in pulse_in Input 1
}
