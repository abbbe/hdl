// ***************************************************************************
// Pulse Counter with Avalon-MM Interface - Simplified Test Version
// ***************************************************************************

`timescale 1ns/100ps

module pulse_counter #(
  parameter COUNTER_WIDTH = 32
) (
  // Avalon-MM Slave Interface
  input                       clk,
  input                       reset_n,
  input                       avs_read,
  input                       avs_write,
  input       [1:0]           avs_address,
  input       [31:0]          avs_writedata,
  output reg  [31:0]          avs_readdata,

  // External pulse input (directly from external clock)
  input                       pulse_in
);

  // Register Map:
  // 0x00: Control Register (bit 0 = enable)
  // 0x04: Status/Version (returns 0xDEADBEEF for test)
  // 0x08: Counter Value
  // 0x0C: Reserved

  // Internal registers
  reg                         ctrl_enable;
  reg [COUNTER_WIDTH-1:0]     counter;

  // Synchronize external pulse input to system clock domain
  reg [2:0] pulse_sync;
  reg       pulse_prev;
  wire      pulse_edge;

  // Synchronizer
  always @(posedge clk or negedge reset_n) begin
    if (!reset_n) begin
      pulse_sync <= 3'b000;
      pulse_prev <= 1'b0;
    end else begin
      pulse_sync <= {pulse_sync[1:0], pulse_in};
      pulse_prev <= pulse_sync[2];
    end
  end

  // Detect rising edge
  assign pulse_edge = pulse_sync[2] & ~pulse_prev;

  // Counter logic
  always @(posedge clk or negedge reset_n) begin
    if (!reset_n) begin
      counter <= {COUNTER_WIDTH{1'b0}};
    end else if (avs_write && avs_address == 2'b00 && avs_writedata[1]) begin
      // Clear counter when bit 1 is written to control reg
      counter <= {COUNTER_WIDTH{1'b0}};
    end else if (ctrl_enable && pulse_edge) begin
      counter <= counter + 1'b1;
    end
  end

  // Control register
  always @(posedge clk or negedge reset_n) begin
    if (!reset_n) begin
      ctrl_enable <= 1'b0;
    end else if (avs_write && avs_address == 2'b00) begin
      ctrl_enable <= avs_writedata[0];
    end
  end

  // Read data mux - purely combinatorial
  always @(*) begin
    case (avs_address)
      2'b00: avs_readdata = {31'b0, ctrl_enable};
      2'b01: avs_readdata = 32'hDEADBEEF;  // Test pattern
      2'b10: avs_readdata = counter[31:0];
      2'b11: avs_readdata = 32'hCAFEBABE;  // Test pattern
    endcase
  end

endmodule
