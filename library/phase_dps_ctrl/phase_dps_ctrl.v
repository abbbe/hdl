// SPDX-License-Identifier: MIT
// Phase DPS Controller - Unified interface for PLL Dynamic Phase Shift
//
// Provides 3-parameter control:
//   - steps: Number of phase shift steps per DPS request (signed)
//   - interval: Clock ticks between DPS requests (0 = one-shot)
//   - count: Number of requests to make (0 = indefinite)
//
// This module acts as an Avalon-MM master to write to the PLL reconfig IP.
// Uses polling of the STATUS register (busy bit) to detect completion.

module phase_dps_ctrl (
    input  wire        clk,
    input  wire        reset,

    // Avalon-MM slave interface (control from Linux)
    input  wire [3:0]  avs_address,
    input  wire        avs_write,
    input  wire [31:0] avs_writedata,
    input  wire        avs_read,
    output reg  [31:0] avs_readdata,

    // Avalon-MM master interface (to PLL reconfig)
    output reg  [5:0]  avm_address,
    output reg         avm_write,
    output reg  [31:0] avm_writedata,
    output reg         avm_read,
    input  wire [31:0] avm_readdata,
    input  wire        avm_waitrequest
);

    // Slave register addresses
    localparam ADDR_STEPS    = 4'h0;  // 0x00
    localparam ADDR_INTERVAL = 4'h1;  // 0x04
    localparam ADDR_COUNT    = 4'h2;  // 0x08
    localparam ADDR_CTRL     = 4'h3;  // 0x0C
    localparam ADDR_STATUS   = 4'h4;  // 0x10
    localparam ADDR_DONE_CNT = 4'h5;  // 0x14

    // PLL reconfig register addresses (word addresses)
    localparam PLL_STATUS_REG = 6'h01;  // Status register (bit 0 = busy)
    localparam PLL_DPS_REG    = 6'h06;  // Dynamic Phase Shift register
    localparam PLL_START_REG  = 6'h02;  // Start register

    // Control bits
    localparam CTRL_START       = 0;
    localparam CTRL_STOP        = 1;
    localparam CTRL_CLEAR_ERROR = 2;

    // State machine states
    localparam STATE_IDLE          = 4'd0;
    localparam STATE_WRITE_DPS     = 4'd1;
    localparam STATE_WAIT_DPS      = 4'd2;
    localparam STATE_WRITE_START   = 4'd3;
    localparam STATE_WAIT_START    = 4'd4;
    localparam STATE_READ_STATUS   = 4'd5;
    localparam STATE_WAIT_READ     = 4'd6;
    localparam STATE_CHECK_BUSY    = 4'd7;
    localparam STATE_WAIT_INTERVAL = 4'd8;
    localparam STATE_CHECK_COUNT   = 4'd9;

    // Configuration registers
    reg signed [15:0] steps;
    reg        [31:0] interval;
    reg        [31:0] count;

    // State
    reg [3:0]  state;
    reg [31:0] tick_counter;
    reg [31:0] request_counter;
    reg [31:0] done_counter;
    reg [15:0] poll_counter;       // Limit polling attempts
    reg        running;
    reg        error;

    // Captured read data
    reg [31:0] read_data;

    // Avalon-MM slave read
    always @(*) begin
        case (avs_address)
            ADDR_STEPS:    avs_readdata = {{16{steps[15]}}, steps};
            ADDR_INTERVAL: avs_readdata = interval;
            ADDR_COUNT:    avs_readdata = count;
            ADDR_CTRL:     avs_readdata = 32'h0;
            ADDR_STATUS:   avs_readdata = {request_counter[15:0], poll_counter[7:0], 6'b0, error, running};
            ADDR_DONE_CNT: avs_readdata = done_counter;
            default:       avs_readdata = 32'h0;
        endcase
    end

    // Main state machine
    always @(posedge clk) begin
        if (reset) begin
            steps <= 16'd1;
            interval <= 32'd0;
            count <= 32'd1;
            state <= STATE_IDLE;
            tick_counter <= 32'd0;
            request_counter <= 32'd0;
            done_counter <= 32'd0;
            poll_counter <= 16'd0;
            running <= 1'b0;
            error <= 1'b0;
            avm_address <= 6'd0;
            avm_write <= 1'b0;
            avm_writedata <= 32'd0;
            avm_read <= 1'b0;
            read_data <= 32'd0;
        end else begin
            // Register writes from Linux
            if (avs_write) begin
                case (avs_address)
                    ADDR_STEPS:    steps <= avs_writedata[15:0];
                    ADDR_INTERVAL: interval <= avs_writedata;
                    ADDR_COUNT:    count <= avs_writedata;
                    ADDR_CTRL: begin
                        if (avs_writedata[CTRL_START] && !running) begin
                            running <= 1'b1;
                            request_counter <= 32'd0;
                            tick_counter <= 32'd0;
                            state <= STATE_WRITE_DPS;
                        end
                        if (avs_writedata[CTRL_STOP]) begin
                            running <= 1'b0;
                            state <= STATE_IDLE;
                            avm_write <= 1'b0;
                            avm_read <= 1'b0;
                        end
                        if (avs_writedata[CTRL_CLEAR_ERROR]) begin
                            error <= 1'b0;
                        end
                    end
                endcase
            end

            // State machine
            case (state)
                STATE_IDLE: begin
                    avm_write <= 1'b0;
                    avm_read <= 1'b0;
                end

                STATE_WRITE_DPS: begin
                    // Build DPS_REG value:
                    // [15:0]  = num_shifts (absolute value)
                    // [20:16] = cnt_sel (0 for C0)
                    // [21]    = up_dn (1=up/advance, 0=down/retard)
                    avm_address <= PLL_DPS_REG;
                    avm_write <= 1'b1;
                    if (steps >= 0) begin
                        avm_writedata <= {10'b0, 1'b1, 5'b0, steps[15:0]};
                    end else begin
                        avm_writedata <= {10'b0, 1'b0, 5'b0, -steps};
                    end
                    state <= STATE_WAIT_DPS;
                end

                STATE_WAIT_DPS: begin
                    if (!avm_waitrequest) begin
                        avm_write <= 1'b0;
                        state <= STATE_WRITE_START;
                    end
                end

                STATE_WRITE_START: begin
                    // Write to START register to trigger DPS
                    avm_address <= PLL_START_REG;
                    avm_write <= 1'b1;
                    avm_writedata <= 32'h1;
                    poll_counter <= 16'd0;
                    state <= STATE_WAIT_START;
                end

                STATE_WAIT_START: begin
                    if (!avm_waitrequest) begin
                        avm_write <= 1'b0;
                        state <= STATE_READ_STATUS;
                    end
                end

                STATE_READ_STATUS: begin
                    // Read STATUS register to check busy bit
                    avm_address <= PLL_STATUS_REG;
                    avm_read <= 1'b1;
                    state <= STATE_WAIT_READ;
                end

                STATE_WAIT_READ: begin
                    if (!avm_waitrequest) begin
                        read_data <= avm_readdata;
                        avm_read <= 1'b0;
                        state <= STATE_CHECK_BUSY;
                    end
                end

                STATE_CHECK_BUSY: begin
                    poll_counter <= poll_counter + 1;
                    if (read_data[0] == 1'b0) begin
                        // Not busy - DPS complete
                        done_counter <= done_counter + 1;
                        request_counter <= request_counter + 1;

                        if (interval == 0) begin
                            state <= STATE_CHECK_COUNT;
                        end else begin
                            tick_counter <= interval;
                            state <= STATE_WAIT_INTERVAL;
                        end
                    end else if (poll_counter >= 16'hFFFF) begin
                        // Timeout - set error flag
                        error <= 1'b1;
                        running <= 1'b0;
                        state <= STATE_IDLE;
                    end else begin
                        // Still busy - poll again
                        state <= STATE_READ_STATUS;
                    end
                end

                STATE_WAIT_INTERVAL: begin
                    if (tick_counter > 0) begin
                        tick_counter <= tick_counter - 1;
                    end else begin
                        state <= STATE_CHECK_COUNT;
                    end
                end

                STATE_CHECK_COUNT: begin
                    if (count == 0) begin
                        // Indefinite mode
                        state <= STATE_WRITE_DPS;
                    end else if (request_counter >= count) begin
                        // Done
                        running <= 1'b0;
                        state <= STATE_IDLE;
                    end else begin
                        state <= STATE_WRITE_DPS;
                    end
                end

                default: begin
                    state <= STATE_IDLE;
                    avm_write <= 1'b0;
                    avm_read <= 1'b0;
                end
            endcase

            // Force stop
            if (!running && state != STATE_IDLE) begin
                state <= STATE_IDLE;
                avm_write <= 1'b0;
                avm_read <= 1'b0;
            end
        end
    end

endmodule
