// ***************************************************************************
// ***************************************************************************
// Copyright (C) 2024 Analog Devices, Inc. All rights reserved.
//
// Phase Measurement Test System for DE10-Nano
// Two PLLs output clocks to GPIO pins for oscilloscope testing
// Internal phase measurement with 200 MHz sampling
//
// ***************************************************************************
// ***************************************************************************

`timescale 1ns/100ps

module system_top (

  // clock and resets
  input            sys_clk,

  // hps-ddr
  output  [14:0]   ddr3_a,
  output  [ 2:0]   ddr3_ba,
  output           ddr3_reset_n,
  output           ddr3_ck_p,
  output           ddr3_ck_n,
  output           ddr3_cke,
  output           ddr3_cs_n,
  output           ddr3_ras_n,
  output           ddr3_cas_n,
  output           ddr3_we_n,
  inout   [31:0]   ddr3_dq,
  inout   [ 3:0]   ddr3_dqs_p,
  inout   [ 3:0]   ddr3_dqs_n,
  output  [ 3:0]   ddr3_dm,
  output           ddr3_odt,
  input            ddr3_rzq,

  // hps-ethernet
  output            eth1_tx_clk,
  output            eth1_tx_ctl,
  output  [  3:0]   eth1_tx_d,
  input             eth1_rx_clk,
  input             eth1_rx_ctl,
  input   [  3:0]   eth1_rx_d,
  output            eth1_mdc,
  inout             eth1_mdio,

  // hps-sdio
  output            sdio_clk,
  inout             sdio_cmd,
  inout   [  3:0]   sdio_d,

  // hps-spim1
  output            spim1_ss0,
  output            spim1_clk,
  output            spim1_mosi,
  input             spim1_miso,

  // hps-usb
  input             usb1_clk,
  output            usb1_stp,
  input             usb1_dir,
  input             usb1_nxt,
  inout   [  7:0]   usb1_d,

  // hps-uart
  input             uart0_rx,
  output            uart0_tx,
  inout             hps_conv_usb_n,

  // board gpio
  output  [  7:0]   gpio_bd_o,
  input   [  5:0]   gpio_bd_i,

  // hdmi (directly connected but unused in this project)
  output            hdmi_out_clk,
  output            hdmi_vsync,
  output            hdmi_hsync,
  output            hdmi_data_e,
  output  [ 23:0]   hdmi_data,

  inout             hdmi_i2c_scl,
  inout             hdmi_i2c_sda,

  // PLL clock outputs to GPIO pins for oscilloscope testing
  // clk_a_out: GPIO_0[25] / PIN_W11 / JP1 pin 28
  // clk_b_out: GPIO_0[9]  / PIN_AH3 / JP1 pin 14
  output            clk_a_out,
  output            clk_b_out
);

  // internal signals
  wire             sys_resetn;
  wire    [63:0]   gpio_i;
  wire    [63:0]   gpio_o;

  wire             i2c0_out_data;
  wire             i2c0_sda;
  wire             i2c0_out_clk;
  wire             i2c0_scl_in_clk;

  // PLL clock signals
  wire             pll_a_clk;
  wire             pll_b_clk;

  // GPIO directly connected
  assign gpio_i[63:14] = gpio_o[63:14];
  assign gpio_i[13:8]  = gpio_bd_i[5:0];
  assign gpio_bd_o[7:0] = gpio_o[7:0];

  // Output PLL clocks to GPIO pins
  // These are directly driven by the PLL outputs
  assign clk_a_out = pll_a_clk;
  assign clk_b_out = pll_b_clk;

  // HDMI I2C buffers (directly connected but unused)
  ALT_IOBUF scl_iobuf (
    .i (1'b0),
    .oe (i2c0_out_clk),
    .o (i2c0_scl_in_clk),
    .io (hdmi_i2c_scl));

  ALT_IOBUF sda_iobuf (
    .i (1'b0),
    .oe (i2c0_out_data),
    .o (i2c0_sda),
    .io (hdmi_i2c_sda));

  system_bd i_system_bd (
    .sys_clk_clk (sys_clk),

    .sys_hps_h2f_reset_reset_n (sys_resetn),

    .sys_hps_memory_mem_a (ddr3_a),
    .sys_hps_memory_mem_ba (ddr3_ba),
    .sys_hps_memory_mem_ck (ddr3_ck_p),
    .sys_hps_memory_mem_ck_n (ddr3_ck_n),
    .sys_hps_memory_mem_cke (ddr3_cke),
    .sys_hps_memory_mem_cs_n (ddr3_cs_n),
    .sys_hps_memory_mem_ras_n (ddr3_ras_n),
    .sys_hps_memory_mem_cas_n (ddr3_cas_n),
    .sys_hps_memory_mem_we_n (ddr3_we_n),
    .sys_hps_memory_mem_reset_n (ddr3_reset_n),
    .sys_hps_memory_mem_dq (ddr3_dq),
    .sys_hps_memory_mem_dqs (ddr3_dqs_p),
    .sys_hps_memory_mem_dqs_n (ddr3_dqs_n),
    .sys_hps_memory_mem_odt (ddr3_odt),
    .sys_hps_memory_mem_dm (ddr3_dm),
    .sys_hps_memory_oct_rzqin (ddr3_rzq),

    .sys_rst_reset_n (sys_resetn),

    .sys_hps_i2c0_out_data (i2c0_out_data),
    .sys_hps_i2c0_sda (i2c0_sda),
    .sys_hps_i2c0_clk_clk (i2c0_out_clk),
    .sys_hps_i2c0_scl_in_clk (i2c0_scl_in_clk),

    .sys_hps_hps_io_hps_io_emac1_inst_TX_CLK (eth1_tx_clk),
    .sys_hps_hps_io_hps_io_emac1_inst_TXD0 (eth1_tx_d[0]),
    .sys_hps_hps_io_hps_io_emac1_inst_TXD1 (eth1_tx_d[1]),
    .sys_hps_hps_io_hps_io_emac1_inst_TXD2 (eth1_tx_d[2]),
    .sys_hps_hps_io_hps_io_emac1_inst_TXD3 (eth1_tx_d[3]),
    .sys_hps_hps_io_hps_io_emac1_inst_RXD0 (eth1_rx_d[0]),
    .sys_hps_hps_io_hps_io_emac1_inst_MDIO (eth1_mdio),
    .sys_hps_hps_io_hps_io_emac1_inst_MDC (eth1_mdc),
    .sys_hps_hps_io_hps_io_emac1_inst_RX_CTL (eth1_rx_ctl),
    .sys_hps_hps_io_hps_io_emac1_inst_TX_CTL (eth1_tx_ctl),
    .sys_hps_hps_io_hps_io_emac1_inst_RX_CLK (eth1_rx_clk),
    .sys_hps_hps_io_hps_io_emac1_inst_RXD1 (eth1_rx_d[1]),
    .sys_hps_hps_io_hps_io_emac1_inst_RXD2 (eth1_rx_d[2]),
    .sys_hps_hps_io_hps_io_emac1_inst_RXD3 (eth1_rx_d[3]),

    .sys_hps_hps_io_hps_io_sdio_inst_CMD (sdio_cmd),
    .sys_hps_hps_io_hps_io_sdio_inst_D0 (sdio_d[0]),
    .sys_hps_hps_io_hps_io_sdio_inst_D1 (sdio_d[1]),
    .sys_hps_hps_io_hps_io_sdio_inst_CLK (sdio_clk),
    .sys_hps_hps_io_hps_io_sdio_inst_D2 (sdio_d[2]),
    .sys_hps_hps_io_hps_io_sdio_inst_D3 (sdio_d[3]),

    .sys_hps_hps_io_hps_io_usb1_inst_D0 (usb1_d[0]),
    .sys_hps_hps_io_hps_io_usb1_inst_D1 (usb1_d[1]),
    .sys_hps_hps_io_hps_io_usb1_inst_D2 (usb1_d[2]),
    .sys_hps_hps_io_hps_io_usb1_inst_D3 (usb1_d[3]),
    .sys_hps_hps_io_hps_io_usb1_inst_D4 (usb1_d[4]),
    .sys_hps_hps_io_hps_io_usb1_inst_D5 (usb1_d[5]),
    .sys_hps_hps_io_hps_io_usb1_inst_D6 (usb1_d[6]),
    .sys_hps_hps_io_hps_io_usb1_inst_D7 (usb1_d[7]),
    .sys_hps_hps_io_hps_io_usb1_inst_CLK (usb1_clk),
    .sys_hps_hps_io_hps_io_usb1_inst_STP (usb1_stp),
    .sys_hps_hps_io_hps_io_usb1_inst_DIR (usb1_dir),
    .sys_hps_hps_io_hps_io_usb1_inst_NXT (usb1_nxt),

    .sys_hps_hps_io_hps_io_uart0_inst_RX (uart0_rx),
    .sys_hps_hps_io_hps_io_uart0_inst_TX (uart0_tx),

    .sys_hps_hps_io_hps_io_spim1_inst_CLK (spim1_clk),
    .sys_hps_hps_io_hps_io_spim1_inst_MOSI (spim1_mosi),
    .sys_hps_hps_io_hps_io_spim1_inst_MISO (spim1_miso),
    .sys_hps_hps_io_hps_io_spim1_inst_SS0 (spim1_ss0),

    .sys_hps_hps_io_hps_io_gpio_inst_GPIO09 (hps_conv_usb_n),

    .sys_gpio_bd_in_port (gpio_i[31:0]),
    .sys_gpio_bd_out_port (gpio_o[31:0]),
    .sys_gpio_in_export (gpio_i[63:32]),
    .sys_gpio_out_export (gpio_o[63:32]),

    // LTC2308 SPI (directly on DE10-Nano board, directly connected)
    .ltc2308_spi_MISO (1'b0),
    .ltc2308_spi_MOSI (),
    .ltc2308_spi_SCLK (),
    .ltc2308_spi_SS_n (),

    // HDMI - directly connected but unused
    .axi_hdmi_tx_0_hdmi_if_h_clk (hdmi_out_clk),
    .axi_hdmi_tx_0_hdmi_if_h24_hsync (hdmi_hsync),
    .axi_hdmi_tx_0_hdmi_if_h24_vsync (hdmi_vsync),
    .axi_hdmi_tx_0_hdmi_if_h24_data_e (hdmi_data_e),
    .axi_hdmi_tx_0_hdmi_if_h24_data (hdmi_data),

    // PLL clock outputs
    .pll_a_clk_clk (pll_a_clk),
    .pll_b_clk_clk (pll_b_clk),

    // Phase measurement clock inputs - internally looped back from PLL outputs
    .clk_a_in_clk_in (pll_a_clk),
    .clk_b_in_clk_in (pll_b_clk)
  );

endmodule
