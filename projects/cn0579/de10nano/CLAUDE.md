# CN0579 DE10-NANO Project - Pulse Counter Extension

## Overview

This project extends the CN0579 ADC capture board firmware for DE10-NANO with a pulse counter module. The pulse counter receives external clock pulses (up to 40MHz), counts them, and makes the count available via Linux userspace through memory-mapped I/O.

## Hardware Configuration

- **Board**: Terasic DE10-NANO (Cyclone V SoC)
- **System Clock**: 50MHz
- **HPS-to-FPGA Bridge**: Lightweight AXI (h2f_lw_axi_master)
- **Base Address**: 0xFF200000 (h2f_lw_axi base)

## Pulse Counter Module

### Location
- Verilog: `hdl/library/pulse_counter/pulse_counter.v`
- Qsys TCL: `hdl/library/pulse_counter/pulse_counter_hw.tcl`

### Features
- 32-bit pulse counter
- 3-stage synchronizer for external asynchronous input
- Rising edge detection
- Enable/disable control
- Counter clear functionality

### Register Map (Base: 0xFF240000)

| Offset | Name    | Access | Description |
|--------|---------|--------|-------------|
| 0x00   | Control | R/W    | bit 0: enable, bit 1: clear counter |
| 0x04   | Status  | R      | Returns 0xDEADBEEF (test pattern) |
| 0x08   | Counter | R      | 32-bit pulse count value |
| 0x0C   | Reserved| R      | Returns 0xCAFEBABE (test pattern) |

### Avalon-MM Interface Settings
- `readLatency`: 0
- `readWaitTime`: 0 (CRITICAL - was 1, caused bus hangs)
- `writeWaitTime`: 0
- Address units: WORDS (4-byte aligned)

## Mock Pulse Generator

For testing purposes, a mock pulse generator is included in `system_top.v`:

```verilog
// Generates ~8.33MHz signal (50MHz / 6)
// Toggle every 3 cycles of sys_clk
localparam USE_MOCK_GENERATOR = 1;
```

To switch to real external input:
1. Set `USE_MOCK_GENERATOR = 0` in `system_top.v`
2. Change `ext_pulse_in` from virtual pin to physical GPIO in `system_project.tcl`

## Userspace Access

```bash
# Read counter value
busybox devmem 0xFF240008

# Enable counting
busybox devmem 0xFF240000 32 0x1

# Disable counting
busybox devmem 0xFF240000 32 0x0

# Clear counter (write while disabled)
busybox devmem 0xFF240000 32 0x2

# Verify test patterns
busybox devmem 0xFF240004  # Should return 0xDEADBEEF
busybox devmem 0xFF24000C  # Should return 0xCAFEBABE
```

## Build Instructions

```bash
# Set Quartus path
export PATH="/opt/altera_lite/24.1std/quartus/bin:$PATH"

# Clean build
cd hdl/projects/cn0579/de10nano
make clean && make

# Output files
# - cn0579_de10nano.sof (JTAG programming)
# - cn0579_de10nano.rbf (FPGA Manager / boot)
```

## Deployment

### Runtime Loading (recommended for testing)
```bash
scp cn0579_de10nano.rbf analog@analog.local:/home/analog/
ssh analog@analog.local
sudo cp /home/analog/cn0579_de10nano.rbf /lib/firmware/
# Note: Runtime loading via /dev/fpga0 may not work on this platform
```

### Boot-time Loading
```bash
# Backup existing FPGA
ssh analog@analog.local "sudo cp /boot/soc_system.rbf /boot/soc_system.rbf.backup"

# Deploy new FPGA
scp cn0579_de10nano.rbf analog@analog.local:/home/analog/
ssh analog@analog.local "sudo cp /home/analog/cn0579_de10nano.rbf /boot/soc_system.rbf"
ssh analog@analog.local "sudo reboot"
```

## Recovery Procedures

### Serial Console Access
- Device: `/dev/ttyUSB0`
- Baud: 115200
- Use `screen`, `minicom`, or Python `pyserial`

### U-Boot Recovery (if board won't boot)
1. Connect serial console
2. Power cycle board
3. Press any key when "Hit any key to stop autoboot" appears
4. Restore backup:
```
fatload mmc 0:1 0x2000000 soc_system.rbf.backup
fatwrite mmc 0:1 0x2000000 soc_system.rbf $filesize
reset
```

## Test Results

With mock generator enabled (~8.33MHz):
- Counter after 1 sec: ~8.96M counts
- Counter after 2 sec: ~17.97M counts
- Effective frequency: ~9 MHz

## Files Modified

| File | Description |
|------|-------------|
| `library/pulse_counter/pulse_counter.v` | Verilog counter module |
| `library/pulse_counter/pulse_counter_hw.tcl` | Qsys component definition |
| `library/pulse_counter/Makefile` | Library build rules |
| `projects/cn0579/de10nano/Makefile` | Added pulse_counter to LIB_DEPS |
| `projects/cn0579/de10nano/system_qsys.tcl` | Instantiates counter at 0x00040000 |
| `projects/cn0579/de10nano/system_top.v` | Mock generator, signal routing |
| `projects/cn0579/de10nano/system_project.tcl` | Virtual pin for ext_pulse_in |

## Known Issues

1. **devmem2 not installed**: Use `busybox devmem` instead
2. **Runtime FPGA loading**: `/dev/fpga0` dd method returns "Invalid argument"; use boot-time loading instead
3. **Kernel module load failures**: Some kernel modules fail to load (unrelated to pulse counter)

## Future Improvements

1. Add physical GPIO pin assignment for `ext_pulse_in`
2. Write Linux kernel driver for cleaner userspace API
3. Add interrupt support for overflow notification
4. Add configurable edge detection (rising/falling/both)
5. Add capture/latch functionality for precise timing measurements

## SSH Access

```
Host: analog@analog.local
Password: analog
```
