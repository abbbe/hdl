#!/usr/bin/env python3
"""
Shared utilities for DE10-Nano Phase Measurement System

Provides interfaces to:
- phase_meas: Edge counting module (500us sample windows)
- phase_dps_ctrl: PLL Dynamic Phase Shift controller
"""

import mmap
import struct
import time

# Memory map addresses (lightweight HPS-to-FPGA bridge)
LW_BRIDGE_BASE = 0xFF200000
PHASE_MEAS_BASE = LW_BRIDGE_BASE + 0x42000
DPS_CTRL_BASE = LW_BRIDGE_BASE + 0x43000

# Phase measurement registers (byte offsets)
PM_CTRL = 0x00       # bit0=enable
PM_STATUS = 0x04     # bits[4:0]=fifo_count, bit5=overflow, bit6=empty
PM_DATA0 = 0x08      # VITA ts low
PM_DATA1 = 0x0C      # VITA ts high
PM_DATA2 = 0x10      # rise_a delta
PM_DATA3 = 0x14      # fall_a delta
PM_DATA4 = 0x18      # rise_b delta
PM_DATA5 = 0x1C      # fall_b delta (reading pops FIFO)
PM_IRQ = 0x20        # bit0=irq_enable, bit1=irq_pending
PM_DBG_RISE_A = 0x24 # raw rising edge counter ch_a
PM_DBG_FALL_A = 0x28 # raw falling edge counter ch_a
PM_DBG_RISE_B = 0x2C # raw rising edge counter ch_b
PM_DBG_FALL_B = 0x30 # raw falling edge counter ch_b

# DPS controller registers (byte offsets)
DPS_REG_STEPS = 0x00
DPS_REG_INTERVAL = 0x04
DPS_REG_COUNT = 0x08
DPS_REG_CTRL = 0x0C
DPS_REG_STATUS = 0x10
DPS_REG_DONE_CNT = 0x14

# DPS control bits
DPS_CTRL_START = 0x01
DPS_CTRL_STOP = 0x02
DPS_CTRL_CLEAR_ERROR = 0x04


class PhaseMeas:
    """Interface to phase_meas module"""

    SAMPLE_INTERVAL_US = 500  # 500us per sample
    EXPECTED_EDGES_PER_SAMPLE = 50000  # At 100 MHz

    def __init__(self):
        self.f = open("/dev/mem", "r+b")
        self.mm = mmap.mmap(self.f.fileno(), 0x100, offset=PHASE_MEAS_BASE)

    def read32(self, off):
        self.mm.seek(off)
        return struct.unpack("<I", self.mm.read(4))[0]

    def write32(self, off, val):
        self.mm.seek(off)
        self.mm.write(struct.pack("<I", val & 0xFFFFFFFF))

    def enable(self):
        """Enable phase measurement"""
        self.write32(PM_CTRL, 1)

    def disable(self):
        """Disable phase measurement"""
        self.write32(PM_CTRL, 0)

    def is_enabled(self):
        """Check if measurement is enabled"""
        return bool(self.read32(PM_CTRL) & 1)

    def get_status(self):
        """Read status register"""
        status = self.read32(PM_STATUS)
        return {
            'fifo_count': status & 0x1F,      # bits[4:0]
            'overflow': bool(status & 0x20),  # bit5
            'empty': bool(status & 0x40),     # bit6
        }

    def read_fifo(self):
        """
        Read one sample from FIFO.
        Returns (vita_ts, rise_a, fall_a, rise_b, fall_b) or None if empty
        """
        status = self.read32(PM_STATUS)
        if status & 0x40:  # empty (bit6)
            return None
        vita_lo = self.read32(PM_DATA0)
        vita_hi = self.read32(PM_DATA1)
        rise_a = self.read32(PM_DATA2)
        fall_a = self.read32(PM_DATA3)
        rise_b = self.read32(PM_DATA4)
        fall_b = self.read32(PM_DATA5)  # pops FIFO
        return ((vita_hi << 32) | vita_lo, rise_a, fall_a, rise_b, fall_b)

    def drain_fifo(self):
        """Read all samples from FIFO"""
        samples = []
        while True:
            s = self.read_fifo()
            if s is None:
                break
            samples.append(s)
        return samples

    def read_debug_counters(self):
        """Read raw edge counters (debug registers)"""
        return {
            'rise_a': self.read32(PM_DBG_RISE_A),
            'fall_a': self.read32(PM_DBG_FALL_A),
            'rise_b': self.read32(PM_DBG_RISE_B),
            'fall_b': self.read32(PM_DBG_FALL_B),
        }

    def close(self):
        self.mm.close()
        self.f.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class DPSControl:
    """Interface to phase_dps_ctrl module"""

    # Phase step size at 400 MHz VCO = 312.5 ps
    # Steps per 100 MHz cycle = 32
    STEP_SIZE_PS = 312.5
    STEPS_PER_CYCLE = 32
    SYS_CLK_HZ = 50_000_000  # 50 MHz system clock

    def __init__(self):
        self.f = open("/dev/mem", "r+b")
        self.mm = mmap.mmap(self.f.fileno(), 0x100, offset=DPS_CTRL_BASE)

    def read32(self, off):
        self.mm.seek(off)
        return struct.unpack("<I", self.mm.read(4))[0]

    def write32(self, off, val):
        self.mm.seek(off)
        self.mm.write(struct.pack("<I", val & 0xFFFFFFFF))

    def get_status(self):
        """Read and decode status register"""
        status = self.read32(DPS_REG_STATUS)
        done_cnt = self.read32(DPS_REG_DONE_CNT)
        return {
            'running': bool(status & 0x01),
            'error': bool(status & 0x02),
            'poll_count': (status >> 8) & 0xFF,
            'request_count': (status >> 16) & 0xFFFF,
            'done_count': done_cnt
        }

    def stop(self):
        """Stop any running DPS operation"""
        self.write32(DPS_REG_CTRL, DPS_CTRL_STOP)
        time.sleep(0.001)

    def clear_error(self):
        """Clear error flag"""
        self.write32(DPS_REG_CTRL, DPS_CTRL_CLEAR_ERROR)

    def start_dps(self, steps, interval_ticks, count):
        """
        Start DPS operation.

        Args:
            steps: Phase steps per request (signed, + = advance, - = retard)
            interval_ticks: Clock ticks (20ns @ 50MHz) between requests (0 = one-shot)
            count: Number of requests (0 = indefinite)
        """
        # Stop any running operation first
        self.stop()
        self.clear_error()

        # Convert signed steps to 16-bit two's complement
        if steps < 0:
            steps_u16 = (1 << 16) + steps
        else:
            steps_u16 = steps & 0xFFFF

        # Write parameters
        self.write32(DPS_REG_STEPS, steps_u16)
        self.write32(DPS_REG_INTERVAL, interval_ticks)
        self.write32(DPS_REG_COUNT, count)

        # Start
        self.write32(DPS_REG_CTRL, DPS_CTRL_START)

    def calc_ppm(self, steps_per_request, interval_ticks):
        """Calculate equivalent PPM for continuous DPS"""
        if interval_ticks == 0:
            return None  # One-shot, not a rate

        interval_sec = interval_ticks / self.SYS_CLK_HZ
        steps_per_sec = abs(steps_per_request) / interval_sec
        phase_drift_sec_per_sec = steps_per_sec * self.STEP_SIZE_PS * 1e-12
        ppm = phase_drift_sec_per_sec * 1e6

        if steps_per_request < 0:
            ppm = -ppm

        return ppm

    def close(self):
        self.mm.close()
        self.f.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def collect_samples(pm, duration_sec, poll_interval=0.05):
    """
    Collect phase measurement samples for a given duration.

    Returns:
        dict with cumulative counts and sample list
    """
    cumulative_a = 0
    cumulative_b = 0
    samples = []

    start_time = time.time()
    while time.time() - start_time < duration_sec:
        time.sleep(poll_interval)
        batch = pm.drain_fifo()
        for s in batch:
            vita, rise_a, fall_a, rise_b, fall_b = s
            cumulative_a += rise_a
            cumulative_b += rise_b
            samples.append(s)

    # Final drain
    batch = pm.drain_fifo()
    for s in batch:
        vita, rise_a, fall_a, rise_b, fall_b = s
        cumulative_a += rise_a
        cumulative_b += rise_b
        samples.append(s)

    return {
        'cumulative_a': cumulative_a,
        'cumulative_b': cumulative_b,
        'drift': cumulative_b - cumulative_a,
        'samples': samples,
        'sample_count': len(samples),
    }
