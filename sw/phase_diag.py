#!/usr/bin/env python3
"""
Phase Measurement Diagnostic Script
Reads debug registers and FIFO to diagnose timing discrepancies
"""

import mmap
import struct
import time

# Memory addresses
LW_BRIDGE_BASE = 0xFF200000
PHASE_MEAS_OFFSET = 0x42000
PHASE_MEAS_BASE = LW_BRIDGE_BASE + PHASE_MEAS_OFFSET

# Register offsets (word addresses * 4)
REG_CTRL = 0x00        # bit0=enable
REG_STATUS = 0x04      # fifo_count, overflow, empty
REG_DATA0 = 0x08       # VITA ts low
REG_DATA1 = 0x0C       # VITA ts high
REG_DATA2 = 0x10       # rise_a delta
REG_DATA3 = 0x14       # fall_a delta
REG_DATA4 = 0x18       # rise_b delta
REG_DATA5 = 0x1C       # fall_b delta (pops FIFO)
REG_IRQ = 0x20         # irq control
REG_DBG_RISE_A = 0x24  # raw rising counter ch_a
REG_DBG_FALL_A = 0x28  # raw falling counter ch_a
REG_DBG_RISE_B = 0x2C  # raw rising counter ch_b
REG_DBG_FALL_B = 0x30  # raw falling counter ch_b
REG_DBG_GATE_CYCLES = 0x34   # computed GATE_CYCLES constant
REG_DBG_SAMPLE_FREQ = 0x38   # SAMPLE_CLK_FREQ parameter


class PhaseMeasDiag:
    def __init__(self):
        self.f = open("/dev/mem", "r+b")
        self.mm = mmap.mmap(self.f.fileno(), 0x100, offset=PHASE_MEAS_BASE)

    def read32(self, offset):
        self.mm.seek(offset)
        return struct.unpack("<I", self.mm.read(4))[0]

    def write32(self, offset, val):
        self.mm.seek(offset)
        self.mm.write(struct.pack("<I", val & 0xFFFFFFFF))

    def enable(self):
        self.write32(REG_CTRL, 1)

    def disable(self):
        self.write32(REG_CTRL, 0)

    def get_status(self):
        status = self.read32(REG_STATUS)
        return {
            'fifo_count': status & 0x1F,
            'overflow': bool(status & 0x20),
            'empty': bool(status & 0x40)
        }

    def read_fifo_entry(self):
        """Read one FIFO entry. Returns None if empty."""
        status = self.get_status()
        if status['empty']:
            return None
        vita_lo = self.read32(REG_DATA0)
        vita_hi = self.read32(REG_DATA1)
        rise_a = self.read32(REG_DATA2)
        fall_a = self.read32(REG_DATA3)
        rise_b = self.read32(REG_DATA4)
        fall_b = self.read32(REG_DATA5)  # pops FIFO
        return {
            'vita': (vita_hi << 32) | vita_lo,
            'rise_a': rise_a,
            'fall_a': fall_a,
            'rise_b': rise_b,
            'fall_b': fall_b
        }

    def drain_fifo(self):
        """Read all FIFO entries."""
        entries = []
        while True:
            entry = self.read_fifo_entry()
            if entry is None:
                break
            entries.append(entry)
        return entries

    def get_debug_counters(self):
        return {
            'rise_a': self.read32(REG_DBG_RISE_A),
            'fall_a': self.read32(REG_DBG_FALL_A),
            'rise_b': self.read32(REG_DBG_RISE_B),
            'fall_b': self.read32(REG_DBG_FALL_B)
        }

    def get_timing_params(self):
        return {
            'gate_cycles': self.read32(REG_DBG_GATE_CYCLES),
            'sample_freq': self.read32(REG_DBG_SAMPLE_FREQ)
        }

    def close(self):
        self.mm.close()
        self.f.close()


def main():
    pm = PhaseMeasDiag()

    print("=" * 60)
    print("Phase Measurement Diagnostic")
    print("=" * 60)

    # Read timing parameters
    print("\n1. Timing Parameters:")
    params = pm.get_timing_params()
    print(f"   GATE_CYCLES = {params['gate_cycles']}")
    print(f"   SAMPLE_CLK_FREQ = {params['sample_freq']}")
    if params['sample_freq'] > 0:
        expected_window_us = (params['gate_cycles'] / params['sample_freq']) * 1_000_000
        print(f"   Expected window = {expected_window_us:.1f} us")
    else:
        print("   WARNING: SAMPLE_CLK_FREQ is 0!")

    # Test debug counter rate
    print("\n2. Debug Counter Rate Test:")
    pm.disable()
    time.sleep(0.1)
    pm.enable()
    time.sleep(0.1)

    cnt1 = pm.get_debug_counters()
    t1 = time.time()
    time.sleep(1.0)
    cnt2 = pm.get_debug_counters()
    t2 = time.time()

    dt = t2 - t1
    rise_rate = (cnt2['rise_a'] - cnt1['rise_a']) / dt
    fall_rate = (cnt2['fall_a'] - cnt1['fall_a']) / dt
    print(f"   Duration: {dt*1000:.1f} ms")
    print(f"   Rise edges: {cnt2['rise_a'] - cnt1['rise_a']}")
    print(f"   Fall edges: {cnt2['fall_a'] - cnt1['fall_a']}")
    print(f"   Rise rate: {rise_rate/1e6:.3f} MHz")
    print(f"   Fall rate: {fall_rate/1e6:.3f} MHz")

    # Read FIFO and analyze
    print("\n3. FIFO Analysis:")
    pm.disable()
    time.sleep(0.1)
    pm.drain_fifo()  # Clear any old data
    pm.enable()
    time.sleep(0.5)  # Let FIFO fill
    pm.disable()

    entries = pm.drain_fifo()
    print(f"   FIFO entries: {len(entries)}")

    if len(entries) >= 2:
        # Analyze VITA timestamp differences
        print("\n   VITA timestamp differences (should be GATE_CYCLES):")
        vita_diffs = []
        for i in range(1, min(len(entries), 6)):
            diff = entries[i]['vita'] - entries[i-1]['vita']
            vita_diffs.append(diff)
            print(f"   Entry {i}: diff = {diff}")

        if vita_diffs:
            avg_diff = sum(vita_diffs) / len(vita_diffs)
            print(f"   Average: {avg_diff:.1f}")
            if params['gate_cycles'] > 0:
                ratio = avg_diff / params['gate_cycles']
                print(f"   Ratio to GATE_CYCLES: {ratio:.3f}")

        # Analyze edge counts
        print("\n   Edge counts per window:")
        for i in range(min(len(entries), 5)):
            e = entries[i]
            print(f"   Entry {i}: rise_a={e['rise_a']}, fall_a={e['fall_a']}, "
                  f"rise_b={e['rise_b']}, fall_b={e['fall_b']}")

        # Calculate expected edges per window
        if params['sample_freq'] > 0 and params['gate_cycles'] > 0:
            window_sec = params['gate_cycles'] / params['sample_freq']
            expected_edges = rise_rate * window_sec
            actual_edges = sum(e['rise_a'] for e in entries) / len(entries)
            print(f"\n   Expected edges/window (based on debug rate): {expected_edges:.1f}")
            print(f"   Actual average edges/window: {actual_edges:.1f}")
            if expected_edges > 0:
                print(f"   Ratio: {actual_edges / expected_edges:.3f}")

    print("\n" + "=" * 60)
    pm.close()


if __name__ == "__main__":
    main()
