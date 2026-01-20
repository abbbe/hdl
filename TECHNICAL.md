# Technical Reference

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                            DE10-Nano                                 │
│                                                                      │
│   50 MHz ──┬──────────────┬──────────────┐                          │
│            │              │              │                          │
│            ▼              ▼              ▼                          │
│     ┌──────────┐   ┌──────────┐   ┌────────────┐                    │
│     │  PLL_A   │   │  PLL_B   │   │ pixel_clk  │                    │
│     │ (40 MHz) │   │ (40 MHz) │   │    _pll    │                    │
│     │ reconfig │   │ reconfig │   │  200 MHz   │                    │
│     │ + DPS    │   │ + DPS    │   │ system clk │                    │
│     └────┬─────┘   └────┬─────┘   └─────┬──────┘                    │
│          │              │               │                           │
│          ▼              ▼               ▼                           │
│     ┌─────────────────────────────────────────┐                     │
│     │        Phase Measurement Core           │                     │
│     │                                         │                     │
│     │  clk_a ──► [2-flop sync] ──► edge_a    │                     │
│     │  clk_b ──► [2-flop sync] ──► edge_b    │                     │
│     │                    │                    │                     │
│     │            200 MHz sample clock         │                     │
│     │                    │                    │                     │
│     │  ┌─────────────────┴─────────────────┐ │                     │
│     │  │  Rise/Fall counters (per channel) │ │                     │
│     │  │  500us gate → compute deltas      │ │                     │
│     │  └─────────────────┬─────────────────┘ │                     │
│     │                    │                    │                     │
│     │                    ▼                    │                     │
│     │  ┌─────────────────────────────────┐   │                     │
│     │  │            FIFO                  │   │                     │
│     │  │  64-bit system tick (5 ns)       │   │                     │
│     │  │  32-bit rise_a delta             │   │                     │
│     │  │  32-bit fall_a delta             │   │                     │
│     │  │  32-bit rise_b delta             │   │                     │
│     │  │  32-bit fall_b delta             │   │                     │
│     │  │  ─────────────────────           │   │                     │
│     │  │  192 bits per sample @ 2 kHz     │   │                     │
│     │  └─────────────────┬───────────────┘   │                     │
│     └────────────────────┼───────────────────┘                     │
│                          │                                          │
│          ┌───────────────┴───────────────┐                         │
│          ▼                               ▼                          │
│     ┌─────────┐                    ┌───────────┐                    │
│     │GPIO OUT │                    │  HPS/ARM  │                    │
│     │ clk_a   │◄── scope probe     │  Linux    │                    │
│     │ clk_b   │◄── scope probe     │           │                    │
│     └─────────┘                    └───────────┘                    │
│                                          │                          │
│                                          ▼                          │
│                                   pll_tuner.py                      │
│                                   - PLL reconfig                    │
│                                   - DPS control                     │
│                                   - Read FIFO                       │
└─────────────────────────────────────────────────────────────────────┘
```

## Design Details

### PLLs
| PLL | Frequency | Purpose | Features |
|-----|-----------|---------|----------|
| PLL_A | 40 MHz | Test clock A | Reconfig, DPS |
| PLL_B | 40 MHz | Test clock B | Reconfig, DPS |
| pixel_clk_pll | 200 MHz | System clock (sampling + tick) | Fixed |

### DPS (Dynamic Phase Shift)

PLL_A and PLL_B support runtime phase adjustment via Altera's Dynamic Phase Shift interface.

| Parameter | Value |
|-----------|-------|
| Step size | 1/8 VCO period (typ. ~125 ps) |
| Steps per cycle | 8 × C_counter (check Quartus report) |
| VCO range | 600-1600 MHz (Cyclone V) |
| Control | Memory-mapped via phase_dps_ctrl |

**Registers (offset 0x43000):**
| Offset | Name | Description |
|--------|------|-------------|
| 0x00 | STEPS | Phase steps per request (signed 16-bit) |
| 0x04 | INTERVAL | Ticks between requests (0=one-shot) |
| 0x08 | COUNT | Number of requests (0=indefinite) |
| 0x0C | CTRL | bit0=start, bit1=stop, bit2=clear_error |
| 0x10 | STATUS | running, error, poll_count |
| 0x14 | DONE_CNT | Completed operations counter |

### GPIO Clock Outputs
| Signal | Pin | GPIO | Purpose |
|--------|-----|------|---------|
| clk_a_out | PIN_W11 | GPIO_0[25] | PLL_A output for oscilloscope |
| clk_b_out | PIN_AH3 | GPIO_0[9] | PLL_B output for oscilloscope |

### Resolution
| Measurement | Resolution | Method |
|-------------|------------|--------|
| Edge timing | 5 ns | 200 MHz sampling |
| Edge count | exact | Free-running counters |
| Frequency | sub-ppb | Fractional-N PLL with DPS |

## Register Map (base 0xFF200000)

### PLL_A Reconfig (offset 0x40000)
### PLL_B Reconfig (offset 0x41000)
Standard Altera PLL reconfig interface.

### Phase Measurement (offset 0x42000)
| Offset | Name | Description |
|--------|------|-------------|
| 0x00 | CTRL | bit0=enable |
| 0x04 | STATUS | [4:0]=fifo_count, bit5=overflow, bit6=empty |
| 0x08 | DATA0 | System tick [31:0] |
| 0x0C | DATA1 | System tick [63:32] |
| 0x10 | DATA2 | Rising edges ch_a delta |
| 0x14 | DATA3 | Falling edges ch_a delta |
| 0x18 | DATA4 | Rising edges ch_b delta |
| 0x1C | DATA5 | Falling edges ch_b delta (pops FIFO) |
| 0x20 | IRQ | bit0=irq_enable, bit1=irq_pending (W1C) |
| 0x24 | DBG_RISE_A | Raw rising edge counter ch_a |
| 0x28 | DBG_FALL_A | Raw falling edge counter ch_a |
| 0x2C | DBG_RISE_B | Raw rising edge counter ch_b |
| 0x30 | DBG_FALL_B | Raw falling edge counter ch_b |

Effectively, DATA0 - DATA5 carry one FIFO entry:

| Field | Bits | Description |
|-------|------|-------------|
| sys_tick | 64 | System tick counter (200 MHz, 5 ns) |
| rise_a | 32 | Rising edge count delta for ch_a |
| fall_a | 32 | Falling edge count delta for ch_a |
| rise_b | 32 | Rising edge count delta for ch_b |
| fall_b | 32 | Falling edge count delta for ch_b |

## Project Structure


```
/home/abb/de10-nanon/hdl-phase/           # HDL repo (branch: phase)
├── CLAUDE.md                              # Project overview
├── TECHNICAL.md                           # This file
├── library/phase_meas/
│   ├── phase_meas.v                       # RTL module
│   ├── phase_meas_hw.tcl                  # Platform Designer wrapper
│   └── Makefile
├── library/phase_dps_ctrl/
│   └── phase_dps_ctrl.v                   # DPS controller
├── projects/phase_meas/de10nano/
│   ├── Makefile
│   ├── system_constr.sdc
│   ├── system_project.tcl
│   ├── system_qsys.tcl
│   └── system_top.v
├── sw/
│   ├── phase_diag.py                      # Diagnostics
│   ├── phase_utils.py                     # DPSControl class
│   ├── pll_tuner.py                       # PLL control
│   └── test_dps.py                        # DPS test suite
└── scripts/
    └── serial_tool.py                     # Serial port tool
```

## Build & Deploy

```bash
# Build FPGA
cd /home/abb/de10-nanon/hdl-phase/projects/phase_meas/de10nano
export PATH=/opt/altera_lite/24.1std/quartus/bin:$PATH
export QSYS_ROOTDIR=/opt/altera_lite/24.1std/quartus/sopc_builder/bin
make

# Deploy to DE10-Nano (requires reboot - FPGA loaded by U-Boot)
scp phase_meas_de10nano.rbf analog@analog.local:~
ssh analog@analog.local "sudo cp /boot/soc_system.rbf /boot/soc_system.rbf.backup && sudo cp ~/phase_meas_de10nano.rbf /boot/soc_system.rbf && sudo reboot"

# Wait ~60s for reboot, then run diagnostics
scp /home/abb/de10-nanon/hdl-phase/sw/phase_diag.py analog@analog.local:~
ssh analog@analog.local "sudo python3 ~/phase_diag.py"
```

## Serial Console Access

**IMPORTANT FOR CLAUDE**: Do NOT use `cat`, `timeout+dd`, or shell-based serial reads - they hang.

Always use the Python pyserial script which handles timeouts properly:

```bash
# Python serial tool (ALWAYS USE THIS FOR CLAUDE)
python3 /home/abb/de10-nanon/hdl-phase/scripts/serial_tool.py read /dev/ttyUSB0 115200 5
python3 /home/abb/de10-nanon/hdl-phase/scripts/serial_tool.py cmd "" /dev/ttyUSB0 115200 3
```

Linux serial console supports SysRQ - you can reboot the board if it is stuck.

**Recovery from bad bitstream**: If board doesn't boot after FPGA update:

1. Check serial console - board may be stuck at U-Boot prompt "=>"
2. Use U-Boot to restore backup:
   ```
   fatload mmc 0:1 0x2000000 soc_system.rbf.backup
   fatwrite mmc 0:1 0x2000000 soc_system.rbf <size_in_hex>
   reset
   ```

## Success Criteria

1. **Edge counting accuracy**: rise_a - fall_a stays within ±1 (no missed edges)
2. **Frequency measurement**: Matches oscilloscope within 1 ppm
3. **No FIFO overflow**: At sustained 2 kHz sample rate
4. **PLL reconfiguration**: Can change frequency from Linux and see effect
5. **DPS operation**: Phase shifts visible in edge count deltas
