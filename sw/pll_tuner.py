#!/usr/bin/env python3
"""
PLL Tuner for DE10-Nano Phase Measurement System
Controls PLL_A and PLL_B frequency via Altera PLL Reconfig IP
Also controls PLL_B Dynamic Phase Shift (DPS) via phase_dps_ctrl module

PLL Reconfig register map (word-addressed, multiply by 4 for byte offset):
  0x00: MODE_REG      - [0]=waitrequest mode
  0x04: STATUS_REG    - [0]=busy
  0x08: START_REG     - write 1 to start reconfig
  0x0C: N_REG         - [7:0]=lo, [15:8]=hi, [16]=bypass, [17]=odd_div
  0x10: M_REG         - [7:0]=lo, [15:8]=hi, [16]=bypass, [17]=odd_div
  0x14: C_COUNTERS_REG - [7:0]=lo, [15:8]=hi, [16]=bypass, [17]=odd_div, [22:18]=cnt_sel
  0x1C: DSM_REG       - [31:0]=K fractional value

DPS Controller register map (offset 0x43000):
  0x00: STEPS     - [15:0]=signed step count per request
  0x04: INTERVAL  - [31:0]=clock ticks between requests (0=one-shot)
  0x08: COUNT     - [31:0]=number of requests (0=indefinite)
  0x0C: CTRL      - [0]=start, [1]=stop, [2]=clear_error
  0x10: STATUS    - [0]=running, [1]=error, [15:8]=poll_count, [31:16]=request_count
  0x14: DONE_CNT  - [31:0]=completed DPS operations
"""
import mmap
import struct
import sys
import time

# Memory map addresses
LW_BRIDGE_BASE = 0xFF200000
PLL_A_BASE = LW_BRIDGE_BASE + 0x40000
PLL_B_BASE = LW_BRIDGE_BASE + 0x41000
DPS_CTRL_BASE = LW_BRIDGE_BASE + 0x43000

# PLL Reconfig register byte offsets (address * 4)
REG_MODE     = 0x00
REG_STATUS   = 0x04
REG_START    = 0x08
REG_N        = 0x0C
REG_M        = 0x10
REG_C        = 0x14
REG_DSM      = 0x1C

# DPS Controller register byte offsets
DPS_REG_STEPS    = 0x00
DPS_REG_INTERVAL = 0x04
DPS_REG_COUNT    = 0x08
DPS_REG_CTRL     = 0x0C
DPS_REG_STATUS   = 0x10
DPS_REG_DONE_CNT = 0x14

# DPS Control bits
DPS_CTRL_START       = 0x01
DPS_CTRL_STOP        = 0x02
DPS_CTRL_CLEAR_ERROR = 0x04

class PLLControl:
    def __init__(self, name, base_addr):
        self.name = name
        self.base = base_addr
        self.f = open("/dev/mem", "r+b")
        self.mm = mmap.mmap(self.f.fileno(), 0x100, offset=base_addr)
        self.ref_freq = 50.0  # 50 MHz reference
    
    def close(self):
        self.mm.close()
        self.f.close()
    
    def read32(self, offset):
        self.mm.seek(offset)
        return struct.unpack("<I", self.mm.read(4))[0]
    
    def write32(self, offset, value):
        self.mm.seek(offset)
        self.mm.write(struct.pack("<I", value & 0xFFFFFFFF))
    
    def is_busy(self):
        return bool(self.read32(REG_STATUS) & 0x01)
    
    def wait_not_busy(self, timeout=1.0):
        start = time.time()
        while time.time() - start < timeout:
            if not self.is_busy():
                return True
            time.sleep(0.001)
        return False
    
    def dump_regs(self):
        print(f"{self.name} registers:")
        for i in range(12):
            val = self.read32(i * 4)
            print(f"  [0x{i*4:02X}] = 0x{val:08X}")
    
    def decode_counter(self, val):
        """Decode counter register to get divider value"""
        lo = val & 0xFF
        hi = (val >> 8) & 0xFF
        bypass = bool(val & 0x10000)
        odd = bool(val & 0x20000)
        if bypass:
            return 1
        return lo + hi  # Total divider
    
    def get_current_config(self):
        """Read current PLL configuration"""
        m_reg = self.read32(REG_M)
        n_reg = self.read32(REG_N)
        dsm_reg = self.read32(REG_DSM)
        
        m = self.decode_counter(m_reg)
        n = self.decode_counter(n_reg) if n_reg else 1
        k = dsm_reg
        
        # Read C0 counter (need to write cnt_sel=0 first, then read back)
        # For now, read from offset 0x28 which is where dump showed C0
        c0_reg = self.read32(0x28)  # CNT_BASE + 0 * 4 in some mappings
        c0 = self.decode_counter(c0_reg) if c0_reg else 4
        
        return {'M': m, 'N': n, 'K': k, 'C0': c0, 
                'M_reg': m_reg, 'N_reg': n_reg, 'DSM_reg': dsm_reg, 'C0_reg': c0_reg}
    
    def calc_freq(self, m, n, k, c0):
        """Calculate output frequency"""
        m_eff = m + k / (2**32)
        vco = self.ref_freq * m_eff / n
        return vco / c0
    
    def set_frequency(self, freq_mhz):
        """
        Set frequency by adjusting M and K values.
        Formula: Fout = Fref * (M + K/2^32) / N / C0
        """
        config = self.get_current_config()
        n = config['N']
        c0 = config['C0']
        
        # Calculate required M+K
        m_total = freq_mhz * n * c0 / self.ref_freq
        m_int = int(m_total)
        m_frac = m_total - m_int
        k = int(m_frac * (2**32)) & 0xFFFFFFFF
        
        # For M counter: lo = hi = m_int/2 (50% duty cycle)
        m_lo = m_int // 2
        m_hi = m_int - m_lo
        m_reg = m_lo | (m_hi << 8)
        
        print(f"Setting {self.name} to {freq_mhz:.6f} MHz")
        print(f"  Current config: M={config['M']}, N={n}, C0={c0}")
        print(f"  New M={m_int} (lo={m_lo}, hi={m_hi}), K=0x{k:08X}")
        expected = self.calc_freq(m_int, n, k, c0)
        print(f"  Expected Fout = {expected:.6f} MHz")
        
        # Wait for not busy
        if not self.wait_not_busy():
            print("  ERROR: PLL busy timeout")
            return False
        
        # Write M counter
        self.write32(REG_M, m_reg)
        time.sleep(0.001)
        
        # Write K (DSM fractional value)
        self.write32(REG_DSM, k)
        time.sleep(0.001)
        
        # Start reconfiguration
        self.write32(REG_START, 1)
        
        # Wait for completion
        time.sleep(0.05)
        if self.wait_not_busy(timeout=0.5):
            print(f"  Reconfiguration complete")
        else:
            print(f"  WARNING: May not have completed")
        
        return True


class DPSControl:
    """Control PLL_B Dynamic Phase Shift via phase_dps_ctrl module"""

    # Phase step size at 400 MHz VCO = 312.5 ps
    # Steps per 100 MHz cycle = 32
    STEP_SIZE_PS = 312.5
    STEPS_PER_CYCLE = 32
    SYS_CLK_HZ = 50_000_000  # 50 MHz system clock

    def __init__(self):
        self.f = open("/dev/mem", "r+b")
        self.mm = mmap.mmap(self.f.fileno(), 0x100, offset=DPS_CTRL_BASE)

    def close(self):
        self.mm.close()
        self.f.close()

    def read32(self, offset):
        self.mm.seek(offset)
        return struct.unpack("<I", self.mm.read(4))[0]

    def write32(self, offset, value):
        self.mm.seek(offset)
        self.mm.write(struct.pack("<I", value & 0xFFFFFFFF))

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
            steps: Number of phase steps per request (signed, negative = retard)
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

        # Rate = steps_per_request / interval_time
        interval_sec = interval_ticks / self.SYS_CLK_HZ
        steps_per_sec = abs(steps_per_request) / interval_sec

        # Each step = STEP_SIZE_PS picoseconds
        # Phase drift per second in seconds:
        phase_drift_sec_per_sec = steps_per_sec * self.STEP_SIZE_PS * 1e-12

        # PPM = fractional frequency offset * 1e6
        # Phase drift of 1 second per second = 1e6 ppm (100% frequency error)
        ppm = phase_drift_sec_per_sec * 1e6

        if steps_per_request < 0:
            ppm = -ppm

        return ppm


def main():
    if len(sys.argv) < 2:
        print("PLL Tuner for DE10-Nano Phase Measurement")
        print("")
        print("Usage: pll_tuner.py <command> [args]")
        print("")
        print("Commands:")
        print("  dump              - Dump PLL registers and decode config")
        print("  status            - Show current frequencies and DPS status")
        print("  set <a|b> <MHz>   - Set PLL frequency")
        print("  offset <ppm>      - Set PLL_B offset from PLL_A (both at 100 MHz base)")
        print("  dps <steps> <interval> <count> - Dynamic Phase Shift on PLL_B")
        print("  dps stop          - Stop continuous DPS")
        print("")
        print("DPS Parameters:")
        print("  steps    - Phase steps per request (signed: + = advance, - = retard)")
        print("  interval - Clock ticks between requests (0 = one-shot)")
        print("             At 50 MHz: 50000 ticks = 1ms, 5000000 ticks = 100ms")
        print("  count    - Number of requests (0 = indefinite)")
        print("")
        print("Examples:")
        print("  pll_tuner.py status")
        print("  pll_tuner.py set b 101       # Set PLL_B to 101 MHz")
        print("  pll_tuner.py offset 100      # Set PLL_B 100ppm faster than PLL_A")
        print("  pll_tuner.py dps 32 0 1      # One-shot: shift 32 steps (one full cycle)")
        print("  pll_tuner.py dps 1 50000 0   # Continuous: 1 step/ms = ~31.2 ppm")
        print("  pll_tuner.py dps -1 50000 0  # Continuous: -1 step/ms = ~-31.2 ppm")
        print("  pll_tuner.py dps stop        # Stop continuous DPS")
        return 1
    
    cmd = sys.argv[1]
    
    pll_a = PLLControl("PLL_A", PLL_A_BASE)
    pll_b = PLLControl("PLL_B", PLL_B_BASE)
    
    try:
        if cmd == "dump":
            pll_a.dump_regs()
            print()
            pll_b.dump_regs()
            
        elif cmd == "status":
            print("Current PLL Configuration:")
            for name, pll in [("PLL_A", pll_a), ("PLL_B", pll_b)]:
                cfg = pll.get_current_config()
                # Note: K (fractional) cannot be read back from PLL reconfig IP
                freq = pll.calc_freq(cfg['M'], cfg['N'], 0, cfg['C0'])
                print(f"  {name}: M={cfg['M']}, N={cfg['N']}, C0={cfg['C0']}")
                print(f"         -> {freq:.6f} MHz (K not readable)")

            # Show DPS status
            try:
                dps = DPSControl()
                status = dps.get_status()
                print()
                print("DPS Controller Status:")
                print(f"  Running: {status['running']}, Error: {status['error']}")
                print(f"  Requests: {status['request_count']}, Done: {status['done_count']}")
                dps.close()
            except Exception as e:
                print(f"  (DPS controller not accessible: {e})")
            
        elif cmd == "set":
            if len(sys.argv) < 4:
                print("Usage: pll_tuner.py set <a|b> <MHz>")
                return 1
            which = sys.argv[2].lower()
            freq = float(sys.argv[3])
            if which == "a":
                pll_a.set_frequency(freq)
            elif which == "b":
                pll_b.set_frequency(freq)
            else:
                print(f"Unknown PLL: {which}")
                return 1
                
        elif cmd == "offset":
            if len(sys.argv) < 3:
                print("Usage: pll_tuner.py offset <ppm>")
                return 1
            ppm = float(sys.argv[2])
            base = 100.0
            freq_b = base * (1 + ppm / 1e6)
            print(f"Setting PLL_A to {base} MHz")
            print(f"Setting PLL_B to {base} + {ppm} ppm = {freq_b:.9f} MHz")
            print(f"  Frequency difference: {ppm * base} Hz")
            print()
            pll_a.set_frequency(base)
            print()
            pll_b.set_frequency(freq_b)

        elif cmd == "dps":
            if len(sys.argv) < 3:
                print("Usage: pll_tuner.py dps <steps> <interval> <count>")
                print("       pll_tuner.py dps stop")
                return 1

            dps = DPSControl()
            try:
                if sys.argv[2] == "stop":
                    dps.stop()
                    status = dps.get_status()
                    print("DPS stopped")
                    print(f"  Final count: {status['done_count']} operations")
                else:
                    if len(sys.argv) < 5:
                        print("Usage: pll_tuner.py dps <steps> <interval> <count>")
                        return 1

                    steps = int(sys.argv[2])
                    interval = int(sys.argv[3])
                    count = int(sys.argv[4])

                    print(f"Starting DPS on PLL_B:")
                    print(f"  Steps per request: {steps}")
                    print(f"  Interval: {interval} ticks ({interval * 20 / 1e6:.3f} ms)")
                    print(f"  Count: {count} {'(indefinite)' if count == 0 else ''}")

                    # Calculate equivalent PPM for continuous mode
                    ppm = dps.calc_ppm(steps, interval)
                    if ppm is not None:
                        print(f"  Equivalent: {ppm:.2f} ppm")
                    else:
                        phase_shift_ps = abs(steps) * DPSControl.STEP_SIZE_PS
                        print(f"  One-shot phase shift: {phase_shift_ps:.1f} ps")

                    dps.start_dps(steps, interval, count)

                    # Wait a moment and show status
                    time.sleep(0.1)
                    status = dps.get_status()
                    print()
                    print(f"Status: running={status['running']}, error={status['error']}")
                    print(f"        requests={status['request_count']}, done={status['done_count']}")
            finally:
                dps.close()

        else:
            print(f"Unknown command: {cmd}")
            return 1
            
    finally:
        pll_a.close()
        pll_b.close()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
