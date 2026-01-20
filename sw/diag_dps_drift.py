#!/usr/bin/env python3
"""
Diagnostic: DPS drift test using raw counters

Tests whether DPS creates measurable drift between PLL_A and PLL_B
by reading the raw edge counters (bypasses FIFO bug).

Usage: sudo python3 diag_dps_drift.py
"""

import sys
import time
sys.path.insert(0, '/home/abb/de10-nanon/hdl-phase/sw')
from phase_utils import PhaseMeas, DPSControl


def test_baseline(pm, duration=2.0):
    """Test drift without DPS - should be near zero"""
    print(f"\n1. Baseline test (no DPS, {duration}s)")
    print("-" * 40)

    c1 = pm.read_debug_counters()
    time.sleep(duration)
    c2 = pm.read_debug_counters()

    delta_a = c2['rise_a'] - c1['rise_a']
    delta_b = c2['rise_b'] - c1['rise_b']
    drift = delta_b - delta_a

    print(f"   Edges A: {delta_a:,}")
    print(f"   Edges B: {delta_b:,}")
    print(f"   Drift (B-A): {drift:+d}")
    print(f"   Expected: ~0")

    return drift


def test_dps_drift(pm, dps, steps, duration=5.0):
    """Test drift with DPS active"""
    direction = "positive" if steps > 0 else "negative"
    print(f"\n2. DPS drift test ({direction}, {duration}s)")
    print("-" * 40)

    c1 = pm.read_debug_counters()
    diff1 = c1['rise_b'] - c1['rise_a']

    print(f"   Starting DPS: {steps:+d} steps per 1ms")
    dps.start_dps(steps, 50000, 0)  # 50000 ticks = 1ms at 50MHz

    time.sleep(duration)

    dps.stop()
    c2 = pm.read_debug_counters()
    diff2 = c2['rise_b'] - c2['rise_a']

    delta_a = c2['rise_a'] - c1['rise_a']
    delta_b = c2['rise_b'] - c1['rise_b']
    drift = delta_b - delta_a

    # Calculate effective PPM
    # At 40 MHz, expected edges = 40e6 * duration
    expected_edges = 40_000_000 * duration
    if expected_edges > 0:
        measured_ppm = (drift / expected_edges) * 1_000_000
    else:
        measured_ppm = 0

    print(f"   Edges A: {delta_a:,}")
    print(f"   Edges B: {delta_b:,}")
    print(f"   Drift (B-A): {drift:+d}")
    print(f"   Measured PPM: {measured_ppm:+.2f}")

    # Expected PPM calculation:
    # 64 steps/ms * 156.25ps/step = 10ns/ms = 10us/s = 10 ppm
    expected_ppm = (abs(steps) / 64) * 10 * (1 if steps > 0 else -1)
    print(f"   Expected PPM: {expected_ppm:+.1f}")

    return drift, measured_ppm


def main():
    print("DPS Drift Diagnostic (Raw Counters)")
    print("=" * 50)

    with PhaseMeas() as pm, DPSControl() as dps:
        # Stop any running DPS
        dps.stop()
        time.sleep(0.1)

        # Test 1: Baseline
        baseline_drift = test_baseline(pm, duration=2.0)

        # Test 2: Positive DPS (+64 steps/ms ~ +10 ppm)
        pos_drift, pos_ppm = test_dps_drift(pm, dps, steps=+64, duration=5.0)

        # Test 3: Negative DPS (-64 steps/ms ~ -10 ppm)
        neg_drift, neg_ppm = test_dps_drift(pm, dps, steps=-64, duration=5.0)

        # Summary
        print("\n" + "=" * 50)
        print("SUMMARY")
        print("=" * 50)
        print(f"Baseline drift:    {baseline_drift:+d} edges")
        print(f"Positive DPS:      {pos_drift:+d} edges ({pos_ppm:+.2f} ppm)")
        print(f"Negative DPS:      {neg_drift:+d} edges ({neg_ppm:+.2f} ppm)")

        # Check results
        ok = True
        if abs(baseline_drift) > 100:
            print("\nWARN: Baseline drift too large")
            ok = False
        if pos_drift < 100:
            print("\nWARN: Positive DPS didn't create positive drift")
            ok = False
        if neg_drift > -100:
            print("\nWARN: Negative DPS didn't create negative drift")
            ok = False

        if ok:
            print("\nDPS is working correctly")
            return 0
        else:
            print("\nDPS may have issues")
            return 1


if __name__ == "__main__":
    sys.exit(main())
