#!/usr/bin/env python3
"""
Quick diagnostic script - checks basic system health
"""

import time
import sys
sys.path.insert(0, '/home/abb/de10-nanon/hdl-phase/sw')

from phase_utils import PhaseMeas, DPSControl

def main():
    print("=" * 60)
    print("Phase Measurement System Diagnostics")
    print("=" * 60)

    # Check phase_meas
    print("\n[Phase Measurement Module]")
    try:
        with PhaseMeas() as pm:
            # Check enable state
            enabled = pm.is_enabled()
            print(f"  Enabled: {enabled}")

            # Check FIFO status
            status = pm.get_status()
            print(f"  FIFO: count={status['fifo_count']}, empty={status['empty']}, overflow={status['overflow']}")

            # Check debug counters
            cnt1 = pm.read_debug_counters()
            print(f"  Raw counters: {cnt1}")

            time.sleep(0.1)
            cnt2 = pm.read_debug_counters()

            delta_a = (cnt2['rise_a'] - cnt1['rise_a']) & 0xFFFFFFFF
            delta_b = (cnt2['rise_b'] - cnt1['rise_b']) & 0xFFFFFFFF

            print(f"  Delta in 100ms: rise_a={delta_a:,}, rise_b={delta_b:,}")

            if delta_a < 1_000_000:
                print("  WARNING: rise_a counter not incrementing as expected!")
                print("           Clock A may not be connected or sampling clock not running")
            else:
                freq_a = delta_a * 10 / 1_000_000
                print(f"  Estimated freq_a: {freq_a:.2f} MHz")

            if delta_b < 1_000_000:
                print("  WARNING: rise_b counter not incrementing as expected!")
                print("           Clock B may not be connected")
            else:
                freq_b = delta_b * 10 / 1_000_000
                print(f"  Estimated freq_b: {freq_b:.2f} MHz")

            # Try to read a sample
            if not enabled:
                pm.enable()
                time.sleep(0.01)

            pm.drain_fifo()  # Clear old
            time.sleep(0.01)

            samples = pm.drain_fifo()
            if samples:
                print(f"  FIFO samples collected: {len(samples)}")
                s = samples[0]
                print(f"  Sample 0: vita={s[0]}, rise_a={s[1]}, fall_a={s[2]}, rise_b={s[3]}, fall_b={s[4]}")
            else:
                print("  WARNING: No FIFO samples collected!")

            pm.disable()

    except Exception as e:
        print(f"  ERROR: {e}")

    # Check DPS controller
    print("\n[DPS Controller]")
    try:
        with DPSControl() as dps:
            status = dps.get_status()
            print(f"  Status: running={status['running']}, error={status['error']}")
            print(f"  Poll count: {status['poll_count']}")
            print(f"  Request count: {status['request_count']}")
            print(f"  Done count: {status['done_count']}")

            # Test one-shot
            print("\n  Testing one-shot DPS...")
            initial_done = status['done_count']
            dps.start_dps(steps=1, interval_ticks=0, count=1)
            time.sleep(0.1)
            status2 = dps.get_status()
            print(f"  After one-shot: done={status2['done_count']} (was {initial_done})")

            if status2['done_count'] == initial_done + 1:
                print("  One-shot: OK")
            else:
                print("  WARNING: One-shot did not complete as expected")

    except Exception as e:
        print(f"  ERROR: {e}")

    print("\n" + "=" * 60)
    print("Diagnostics complete")

if __name__ == "__main__":
    main()
