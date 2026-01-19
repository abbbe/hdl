// Phase Measurement System
// Samples two clock signals at 200 MHz and counts rising/falling edges
// Outputs edge counts and phase difference to FIFO at 2 kHz
//
// Register Map (from HPS via Avalon-MM):
//   0x00: CTRL     (R/W) - bit0=enable, bit1=clear_fifo
//   0x04: STATUS   (R)   - bits[3:0]=fifo_count, bit4=overflow, bit5=fifo_empty
//   0x08: DATA0    (R)   - VITA timestamp [31:0]
//   0x0C: DATA1    (R)   - VITA timestamp [63:32]
//   0x10: DATA2    (R)   - Rise edges ch_a delta [31:0]
//   0x14: DATA3    (R)   - Fall edges ch_a delta [31:0]
//   0x18: DATA4    (R)   - Rise edges ch_b delta [31:0]
//   0x1C: DATA5    (R)   - Fall edges ch_b delta [31:0] - reading pops FIFO
//   0x20: IRQ      (R/W) - bit0=irq_enable, bit1=irq_pending (W1C)
//   0x24: DBG_RISE_A (R) - raw rising edge counter ch_a
//   0x28: DBG_FALL_A (R) - raw falling edge counter ch_a
//   0x2C: DBG_RISE_B (R) - raw rising edge counter ch_b
//   0x30: DBG_FALL_B (R) - raw falling edge counter ch_b

module phase_meas #(
    parameter SAMPLE_CLK_FREQ   = 200000000,  // 200 MHz sampling clock
    parameter SAMPLE_INTERVAL_US = 500        // Sample interval in microseconds
) (
    // 200 MHz sampling clock
    input  wire        sample_clk,
    input  wire        reset,

    // Avalon-MM slave interface (50 MHz sys_clk domain)
    input  wire        avs_clk,
    input  wire        avs_reset,
    input  wire [4:0]  avs_address,
    input  wire        avs_read,
    output reg  [31:0] avs_readdata,
    input  wire        avs_write,
    input  wire [31:0] avs_writedata,

    // Clock inputs to measure
    input  wire        clk_a_in,
    input  wire        clk_b_in,

    // Interrupt output
    output wire        irq
);

    // Calculate gate cycles for sample interval
    localparam GATE_CYCLES = (SAMPLE_CLK_FREQ / 1000000) * SAMPLE_INTERVAL_US;
    localparam GATE_WIDTH  = $clog2(GATE_CYCLES) + 1;

    // FIFO parameters
    localparam FIFO_DEPTH = 16;
    localparam FIFO_ADDR_WIDTH = 4;

    // =========================================================================
    // 200 MHz Sample Clock Domain
    // =========================================================================

    // Reset synchronizer for sample clock domain
    reg [2:0] reset_sync;
    wire      sample_reset;

    always @(posedge sample_clk) begin
        reset_sync <= {reset_sync[1:0], reset};
    end
    assign sample_reset = reset_sync[2];

    // 2-stage synchronizers for clock inputs (proper metastability protection)
    reg [1:0] clk_a_sync;
    reg [1:0] clk_b_sync;

    always @(posedge sample_clk) begin
        if (sample_reset) begin
            clk_a_sync <= 2'b00;
            clk_b_sync <= 2'b00;
        end else begin
            clk_a_sync <= {clk_a_sync[0], clk_a_in};
            clk_b_sync <= {clk_b_sync[0], clk_b_in};
        end
    end

    // Edge detection
    reg clk_a_prev, clk_b_prev;
    wire rise_a, fall_a, rise_b, fall_b;

    always @(posedge sample_clk) begin
        if (sample_reset) begin
            clk_a_prev <= 1'b0;
            clk_b_prev <= 1'b0;
        end else begin
            clk_a_prev <= clk_a_sync[1];
            clk_b_prev <= clk_b_sync[1];
        end
    end

    assign rise_a = clk_a_sync[1] & ~clk_a_prev;
    assign fall_a = ~clk_a_sync[1] & clk_a_prev;
    assign rise_b = clk_b_sync[1] & ~clk_b_prev;
    assign fall_b = ~clk_b_sync[1] & clk_b_prev;

    // Edge counters (free-running)
    reg [31:0] rise_cnt_a, fall_cnt_a;
    reg [31:0] rise_cnt_b, fall_cnt_b;

    always @(posedge sample_clk) begin
        if (sample_reset) begin
            rise_cnt_a <= 32'd0;
            fall_cnt_a <= 32'd0;
            rise_cnt_b <= 32'd0;
            fall_cnt_b <= 32'd0;
        end else begin
            rise_cnt_a <= rise_cnt_a + rise_a;
            fall_cnt_a <= fall_cnt_a + fall_a;
            rise_cnt_b <= rise_cnt_b + rise_b;
            fall_cnt_b <= fall_cnt_b + fall_b;
        end
    end

    // VITA timestamp (200 MHz)
    reg [63:0] vita_counter;

    always @(posedge sample_clk) begin
        if (sample_reset) begin
            vita_counter <= 64'd0;
        end else begin
            vita_counter <= vita_counter + 64'd1;
        end
    end

    // Gate timer
    reg [GATE_WIDTH-1:0] gate_counter;
    wire                 gate_expired;

    assign gate_expired = (gate_counter >= GATE_CYCLES - 1);

    // Enable synchronizer from avs_clk domain
    reg [2:0] enable_sync;
    wire      enable_sample;

    always @(posedge sample_clk) begin
        enable_sync <= {enable_sync[1:0], enable};
    end
    assign enable_sample = enable_sync[2];

    always @(posedge sample_clk) begin
        if (sample_reset) begin
            gate_counter <= 0;
        end else if (!enable_sample) begin
            gate_counter <= 0;
        end else if (gate_expired) begin
            gate_counter <= 0;
        end else begin
            gate_counter <= gate_counter + 1;
        end
    end

    // Sample capture registers
    reg [31:0] rise_prev_a, fall_prev_a;
    reg [31:0] rise_prev_b, fall_prev_b;
    reg [31:0] rise_delta_a, fall_delta_a;
    reg [31:0] rise_delta_b, fall_delta_b;
    reg [63:0] vita_sample;

    // FIFO write signals (sample clock domain)
    reg        fifo_wr_en;
    reg [4:0]  fifo_wr_ptr;
    wire       fifo_full_sample;

    // FIFO storage (crossing to avs_clk domain)
    reg [63:0] fifo_vita  [0:FIFO_DEPTH-1];
    reg [31:0] fifo_rise_a [0:FIFO_DEPTH-1];
    reg [31:0] fifo_fall_a [0:FIFO_DEPTH-1];
    reg [31:0] fifo_rise_b [0:FIFO_DEPTH-1];
    reg [31:0] fifo_fall_b [0:FIFO_DEPTH-1];

    // Sample and write to FIFO
    always @(posedge sample_clk) begin
        if (sample_reset) begin
            rise_prev_a <= 32'd0;
            fall_prev_a <= 32'd0;
            rise_prev_b <= 32'd0;
            fall_prev_b <= 32'd0;
            fifo_wr_ptr <= 0;
            fifo_wr_en <= 1'b0;
        end else if (!enable_sample) begin
            rise_prev_a <= rise_cnt_a;
            fall_prev_a <= fall_cnt_a;
            rise_prev_b <= rise_cnt_b;
            fall_prev_b <= fall_cnt_b;
            fifo_wr_ptr <= 0;
            fifo_wr_en <= 1'b0;
        end else if (gate_expired) begin
            // Compute deltas
            rise_delta_a <= rise_cnt_a - rise_prev_a;
            fall_delta_a <= fall_cnt_a - fall_prev_a;
            rise_delta_b <= rise_cnt_b - rise_prev_b;
            fall_delta_b <= fall_cnt_b - fall_prev_b;
            vita_sample <= vita_counter;

            // Update previous values
            rise_prev_a <= rise_cnt_a;
            fall_prev_a <= fall_cnt_a;
            rise_prev_b <= rise_cnt_b;
            fall_prev_b <= fall_cnt_b;

            // Write to FIFO if not full
            if (!fifo_full_sample) begin
                fifo_vita[fifo_wr_ptr[FIFO_ADDR_WIDTH-1:0]] <= vita_counter;
                fifo_rise_a[fifo_wr_ptr[FIFO_ADDR_WIDTH-1:0]] <= rise_cnt_a - rise_prev_a;
                fifo_fall_a[fifo_wr_ptr[FIFO_ADDR_WIDTH-1:0]] <= fall_cnt_a - fall_prev_a;
                fifo_rise_b[fifo_wr_ptr[FIFO_ADDR_WIDTH-1:0]] <= rise_cnt_b - rise_prev_b;
                fifo_fall_b[fifo_wr_ptr[FIFO_ADDR_WIDTH-1:0]] <= fall_cnt_b - fall_prev_b;
                fifo_wr_ptr <= fifo_wr_ptr + 1;
                fifo_wr_en <= 1'b1;
            end
        end else begin
            fifo_wr_en <= 1'b0;
        end
    end

    // =========================================================================
    // AVS Clock Domain (50 MHz sys_clk)
    // =========================================================================

    // Control/status registers
    reg        enable;
    reg        irq_enable;
    reg        irq_pending;
    reg        overflow;

    // FIFO read pointer (avs_clk domain)
    reg [4:0]  fifo_rd_ptr;
    reg        fifo_pop;

    // Synchronize write pointer to avs_clk domain
    reg [4:0]  fifo_wr_ptr_sync1, fifo_wr_ptr_sync2;

    always @(posedge avs_clk) begin
        if (avs_reset) begin
            fifo_wr_ptr_sync1 <= 0;
            fifo_wr_ptr_sync2 <= 0;
        end else begin
            fifo_wr_ptr_sync1 <= fifo_wr_ptr;
            fifo_wr_ptr_sync2 <= fifo_wr_ptr_sync1;
        end
    end

    // FIFO status
    wire [4:0] fifo_count;
    wire       fifo_empty;
    wire       fifo_full;

    assign fifo_count = fifo_wr_ptr_sync2 - fifo_rd_ptr;
    assign fifo_empty = (fifo_count == 0);
    assign fifo_full  = (fifo_count >= FIFO_DEPTH);
    assign fifo_full_sample = fifo_full;  // Cross-domain approximation

    // Current FIFO output
    wire [63:0] rd_vita;
    wire [31:0] rd_rise_a, rd_fall_a;
    wire [31:0] rd_rise_b, rd_fall_b;

    assign rd_vita   = fifo_vita[fifo_rd_ptr[FIFO_ADDR_WIDTH-1:0]];
    assign rd_rise_a = fifo_rise_a[fifo_rd_ptr[FIFO_ADDR_WIDTH-1:0]];
    assign rd_fall_a = fifo_fall_a[fifo_rd_ptr[FIFO_ADDR_WIDTH-1:0]];
    assign rd_rise_b = fifo_rise_b[fifo_rd_ptr[FIFO_ADDR_WIDTH-1:0]];
    assign rd_fall_b = fifo_fall_b[fifo_rd_ptr[FIFO_ADDR_WIDTH-1:0]];

    // Synchronize raw counters to avs_clk for debug reads
    reg [31:0] rise_cnt_a_sync, fall_cnt_a_sync;
    reg [31:0] rise_cnt_b_sync, fall_cnt_b_sync;

    always @(posedge avs_clk) begin
        rise_cnt_a_sync <= rise_cnt_a;
        fall_cnt_a_sync <= fall_cnt_a;
        rise_cnt_b_sync <= rise_cnt_b;
        fall_cnt_b_sync <= fall_cnt_b;
    end

    // FIFO read pointer management
    always @(posedge avs_clk) begin
        if (avs_reset) begin
            fifo_rd_ptr <= 0;
        end else if (!enable) begin
            fifo_rd_ptr <= 0;
        end else if (fifo_pop && !fifo_empty) begin
            fifo_rd_ptr <= fifo_rd_ptr + 1;
        end
    end

    // Interrupt logic
    reg fifo_wr_en_sync1, fifo_wr_en_sync2, fifo_wr_en_prev;

    always @(posedge avs_clk) begin
        if (avs_reset) begin
            fifo_wr_en_sync1 <= 1'b0;
            fifo_wr_en_sync2 <= 1'b0;
            fifo_wr_en_prev <= 1'b0;
            irq_pending <= 1'b0;
        end else begin
            fifo_wr_en_sync1 <= fifo_wr_en;
            fifo_wr_en_sync2 <= fifo_wr_en_sync1;
            fifo_wr_en_prev <= fifo_wr_en_sync2;

            if (avs_write && avs_address == 5'h08 && avs_writedata[1]) begin
                // W1C: Clear interrupt
                irq_pending <= 1'b0;
            end else if (fifo_wr_en_sync2 && !fifo_wr_en_prev) begin
                // Set interrupt on new sample
                irq_pending <= 1'b1;
            end
        end
    end

    assign irq = irq_enable & irq_pending;

    // Overflow tracking
    always @(posedge avs_clk) begin
        if (avs_reset) begin
            overflow <= 1'b0;
        end else if (!enable) begin
            overflow <= 1'b0;
        end else if (fifo_full && fifo_wr_en_sync2 && !fifo_wr_en_prev) begin
            overflow <= 1'b1;
        end
    end

    // Avalon-MM write interface
    always @(posedge avs_clk) begin
        if (avs_reset) begin
            enable <= 1'b0;
            irq_enable <= 1'b0;
        end else if (avs_write) begin
            case (avs_address)
                5'h00: begin
                    enable <= avs_writedata[0];
                end
                5'h08: begin
                    irq_enable <= avs_writedata[0];
                end
                default: ;
            endcase
        end
    end

    // Avalon-MM read interface
    always @(*) begin
        fifo_pop = 1'b0;
        case (avs_address)
            5'h00: avs_readdata = {31'd0, enable};
            5'h01: avs_readdata = {26'd0, fifo_empty, overflow, fifo_count[3:0]};
            5'h02: avs_readdata = rd_vita[31:0];
            5'h03: avs_readdata = rd_vita[63:32];
            5'h04: avs_readdata = rd_rise_a;
            5'h05: avs_readdata = rd_fall_a;
            5'h06: avs_readdata = rd_rise_b;
            5'h07: begin
                avs_readdata = rd_fall_b;
                fifo_pop = avs_read;  // Pop FIFO when reading DATA5
            end
            5'h08: avs_readdata = {30'd0, irq_pending, irq_enable};
            5'h09: avs_readdata = rise_cnt_a_sync;  // DEBUG: raw rising counter ch_a
            5'h0A: avs_readdata = fall_cnt_a_sync;  // DEBUG: raw falling counter ch_a
            5'h0B: avs_readdata = rise_cnt_b_sync;  // DEBUG: raw rising counter ch_b
            5'h0C: avs_readdata = fall_cnt_b_sync;  // DEBUG: raw falling counter ch_b
            default: avs_readdata = 32'd0;
        endcase
    end

endmodule
