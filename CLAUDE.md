# DE10-Nano Phase Measurement Test System

## Testbed

- **Board**: DE10-Nano (Cyclone V SoC - 5CSEBA6U23I7)
- **SSH access**: `ssh analog@analog.local`
- **Serial console**: `/dev/ttyUSB0` (115200 baud)
- **Host**: Linux development machine

## Project Goals

1. Develop and validate phase measurement between two clock signals
2. Test PLL fine-tuning capabilities (frequency and phase control)
3. Build foundation for multi-site N210 clock synchronization
4. Characterize edge counting resolution and noise on Cyclone V

## Architecture

Note: Uses h2f_user2_clk (100 MHz from HPS) for sampling to stay within
the 3 fractional PLL limit on Cyclone V (pixel_clk_pll + pll_a + pll_b).

```
┌─────────────────────────────────────────────────────────────────────┐
│                            DE10-Nano                                 │
│                                                                      │
│   50 MHz ──┬──────────────┬                                         │
│            │              │         ┌── HPS ────────────┐           │
│            ▼              ▼         │ h2f_user2_clk     │           │
│     ┌──────────┐   ┌──────────┐     │ (100 MHz)         │           │
│     │  PLL_A   │   │  PLL_B   │     └────────┬──────────┘           │
│     │ (100MHz) │   │ (100MHz) │              │                      │
│     │ reconfig │   │ reconfig │              │                      │
│     └────┬─────┘   └────┬─────┘              │                      │
│          │              │                    │                      │
│          ▼              ▼                    ▼                      │
│     ┌─────────────────────────────────────────┐                     │
│     │        Phase Measurement Core           │                     │
│     │                                         │                     │
│     │  clk_a ──► [2-flop sync] ──► edge_a    │                     │
│     │  clk_b ──► [2-flop sync] ──► edge_b    │                     │
│     │                    │                    │                     │
│     │            100 MHz sample clock         │                     │
│     │                    │                    │                     │
│     │  ┌─────────────────┴─────────────────┐ │                     │
│     │  │  Rise/Fall counters (per channel) │ │                     │
│     │  │  500us gate → compute deltas      │ │                     │
│     │  └─────────────────┬─────────────────┘ │                     │
│     │                    │                    │                     │
│     │                    ▼                    │                     │
│     │  ┌─────────────────────────────────┐   │                     │
│     │  │            FIFO                  │   │                     │
│     │  │  64-bit VITA timestamp           │   │                     │
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
│                                   - Read FIFO                       │
│                                   - Statistics                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Design Details

### PLLs
| PLL | Frequency | Purpose | Reconfig |
|-----|-----------|---------|----------|
| PLL_A | 100 MHz | Clock output A | Yes (from Linux) |
| PLL_B | 100 MHz | Clock output B | Yes (from Linux) |
| h2f_user2_clk | 100 MHz | Edge sampling | No (HPS clock) |

Note: Cyclone V 5CSEBA6 has only 3 fractional PLL locations. The base system
uses pixel_clk_pll for HDMI, leaving 2 for pll_a and pll_b. Sampling uses
the HPS-provided h2f_user2_clk instead of a dedicated PLL.

### GPIO Clock Outputs
| Signal | Pin | GPIO | Purpose |
|--------|-----|------|---------|
| clk_a_out | PIN_W11 | GPIO_0[25] | PLL_A output for oscilloscope |
| clk_b_out | PIN_AH3 | GPIO_0[9] | PLL_B output for oscilloscope |

### FIFO Payload (192 bits per sample)
| Field | Bits | Description |
|-------|------|-------------|
| vita_ts | 64 | VITA-49 timestamp (200 MHz ticks) |
| rise_a | 32 | Rising edge count delta for ch_a |
| fall_a | 32 | Falling edge count delta for ch_a |
| rise_b | 32 | Rising edge count delta for ch_b |
| fall_b | 32 | Falling edge count delta for ch_b |

### Resolution
| Measurement | Resolution | Method |
|-------------|------------|--------|
| Edge timing | 10 ns | 100 MHz sampling (h2f_user2_clk) |
| Edge count | exact | Free-running counters |
| Frequency | sub-ppb | Fractional-N PLL |

## Register Map (base 0xFF200000)

### PLL_A Reconfig (offset 0x40000)
### PLL_B Reconfig (offset 0x41000)
Standard Altera PLL reconfig interface.

### Phase Measurement (offset 0x42000)
| Offset | Name | Description |
|--------|------|-------------|
| 0x00 | CTRL | bit0=enable |
| 0x04 | STATUS | [3:0]=fifo_count, bit4=overflow, bit5=empty |
| 0x08 | DATA0 | VITA timestamp [31:0] |
| 0x0C | DATA1 | VITA timestamp [63:32] |
| 0x10 | DATA2 | Rising edges ch_a delta |
| 0x14 | DATA3 | Falling edges ch_a delta |
| 0x18 | DATA4 | Rising edges ch_b delta |
| 0x1C | DATA5 | Falling edges ch_b delta (pops FIFO) |
| 0x20 | IRQ | bit0=irq_enable, bit1=irq_pending (W1C) |
| 0x24 | DBG_RISE_A | Raw rising edge counter ch_a |
| 0x28 | DBG_FALL_A | Raw falling edge counter ch_a |
| 0x2C | DBG_RISE_B | Raw rising edge counter ch_b |
| 0x30 | DBG_FALL_B | Raw falling edge counter ch_b |

## Project Structure

```
/home/abb/de10-nanon/hdl-phase/           # HDL repo (branch: phase)
├── CLAUDE.md                              # This file
├── library/phase_meas/
│   ├── phase_meas.v                       # RTL module
│   ├── phase_meas_hw.tcl                  # Platform Designer wrapper
│   └── Makefile
├── projects/phase_meas/de10nano/
│   ├── Makefile
│   ├── system_constr.sdc
│   ├── system_project.tcl
│   ├── system_qsys.tcl
│   └── system_top.v
└── scripts/
    └── serial_tool.py                     # Serial port tool for debugging
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

# Wait ~60s for reboot, then run monitoring
scp /home/abb/de10-nanon/sw/pll_tuner.py analog@analog.local:~
ssh analog@analog.local "sudo python3 pll_tuner.py monitor"
```

## Serial Console Access

**IMPORTANT FOR CLAUDE**: Do NOT use `cat`, `timeout+dd`, or shell-based serial reads - they hang without PTY.
Always use the Python pyserial script which handles timeouts properly:

```bash
# Python serial tool (ALWAYS USE THIS FOR CLAUDE)
python3 /home/abb/de10-nanon/hdl-phase/scripts/serial_tool.py read /dev/ttyUSB0 115200 5
python3 /home/abb/de10-nanon/hdl-phase/scripts/serial_tool.py cmd "" /dev/ttyUSB0 115200 3
python3 /home/abb/de10-nanon/hdl-phase/scripts/serial_tool.py cmd "help" /dev/ttyUSB0 115200 2

# Interactive (for user only, not Claude)
cu -l /dev/ttyUSB0 -s 115200   # Exit with ~.
```

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

## Development Log

### 2026-01-19: Initial Bring-up
- Build successful with full base system (including HDMI)
- Fixed PLL resource overflow by using h2f_user2_clk for sampling
- Edge counting verified working on DE10-Nano
- Issue: Measured frequency is 33.33 MHz instead of expected 100 MHz
  - Both channels show consistent 33.33 MHz = 100/3 MHz
  - Need oscilloscope to verify actual PLL output
  - Possible causes: PLL misconfiguration, h2f_user2_clk rate, aliasing
