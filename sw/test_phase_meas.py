#!/usr/bin/env python3
"""
Phase Measurement Module Tests

Tests basic functionality of phase_meas module:
- Debug counters incrementing
- FIFO operation
- Edge counting accuracy
"""

import pytest
import time
import sys
sys.path.insert(0, '/home/abb/de10-nanon/hdl-phase/sw')

from phase_utils import PhaseMeas, collect_samples


class TestDebugCounters:
    """Test raw debug counters are incrementing"""

    def test_counters_incrementing(self):
        """Verify debug counters change over time (clocks connected)"""
        with PhaseMeas() as pm:
            # Read counters twice with delay
            cnt1 = pm.read_debug_counters()
            time.sleep(0.1)
            cnt2 = pm.read_debug_counters()

            print(f"\nCounter snapshot 1: {cnt1}")
            print(f"Counter snapshot 2: {cnt2}")

            # At 100 MHz, expect ~10M edges in 0.1s
            # Check that counters changed
            delta_rise_a = (cnt2['rise_a'] - cnt1['rise_a']) & 0xFFFFFFFF
            delta_rise_b = (cnt2['rise_b'] - cnt1['rise_b']) & 0xFFFFFFFF

            print(f"Delta rise_a: {delta_rise_a}")
            print(f"Delta rise_b: {delta_rise_b}")

            # Should see ~10M edges, allow wide tolerance
            assert delta_rise_a > 1_000_000, f"rise_a not incrementing: delta={delta_rise_a}"
            assert delta_rise_b > 1_000_000, f"rise_b not incrementing: delta={delta_rise_b}"

    def test_counter_rates(self):
        """Verify counters increment at expected ~100 MHz rate"""
        with PhaseMeas() as pm:
            cnt1 = pm.read_debug_counters()
            time.sleep(1.0)
            cnt2 = pm.read_debug_counters()

            delta_rise_a = (cnt2['rise_a'] - cnt1['rise_a']) & 0xFFFFFFFF
            delta_rise_b = (cnt2['rise_b'] - cnt1['rise_b']) & 0xFFFFFFFF

            # Expect ~100M edges/sec, allow 1% tolerance
            expected = 100_000_000
            tolerance = 0.01

            print(f"\nrise_a rate: {delta_rise_a:,} Hz")
            print(f"rise_b rate: {delta_rise_b:,} Hz")
            print(f"Expected: {expected:,} Hz (+/- {tolerance*100}%)")

            assert abs(delta_rise_a - expected) < expected * tolerance, \
                f"rise_a rate off: {delta_rise_a} vs {expected}"
            assert abs(delta_rise_b - expected) < expected * tolerance, \
                f"rise_b rate off: {delta_rise_b} vs {expected}"


class TestFifo:
    """Test FIFO operation"""

    def test_fifo_fills_when_enabled(self):
        """FIFO should fill with samples when enabled"""
        with PhaseMeas() as pm:
            pm.disable()
            time.sleep(0.01)
            pm.drain_fifo()

            # Enable and wait for samples
            pm.enable()
            time.sleep(0.1)  # Should get ~200 samples at 2kHz

            status = pm.get_status()
            print(f"\nStatus after 100ms: {status}")

            # FIFO depth is 16, should be non-empty
            assert not status['empty'], "FIFO should not be empty after 100ms"

            samples = pm.drain_fifo()
            print(f"Drained {len(samples)} samples")

            pm.disable()

            assert len(samples) > 0, "Should have collected samples"

    def test_sample_values(self):
        """Verify sample values are reasonable"""
        with PhaseMeas() as pm:
            pm.disable()
            time.sleep(0.01)
            pm.drain_fifo()

            pm.enable()
            time.sleep(0.1)

            samples = pm.drain_fifo()
            pm.disable()

            print(f"\nCollected {len(samples)} samples")
            if samples:
                # Check first few samples
                for i, s in enumerate(samples[:5]):
                    vita, rise_a, fall_a, rise_b, fall_b = s
                    print(f"  [{i}] vita={vita}, rise_a={rise_a}, fall_a={fall_a}, "
                          f"rise_b={rise_b}, fall_b={fall_b}")

                # At 100 MHz with 500us window, expect ~50000 edges per sample
                expected = 50000
                tolerance = 100  # Allow some jitter

                for i, s in enumerate(samples):
                    vita, rise_a, fall_a, rise_b, fall_b = s
                    assert abs(rise_a - expected) < tolerance, \
                        f"Sample {i}: rise_a={rise_a}, expected ~{expected}"
                    assert abs(rise_b - expected) < tolerance, \
                        f"Sample {i}: rise_b={rise_b}, expected ~{expected}"


class TestBaseline:
    """Baseline tests - both clocks at same frequency, no DPS"""

    def test_baseline_drift(self):
        """With no DPS, cumulative drift should be near zero"""
        with PhaseMeas() as pm:
            pm.disable()
            time.sleep(0.01)
            pm.drain_fifo()

            pm.enable()
            result = collect_samples(pm, duration_sec=5.0)
            pm.disable()

            print(f"\nBaseline test (5 seconds):")
            print(f"  Samples collected: {result['sample_count']}")
            print(f"  Cumulative rise_a: {result['cumulative_a']:,}")
            print(f"  Cumulative rise_b: {result['cumulative_b']:,}")
            print(f"  Drift (b - a): {result['drift']}")

            # Drift should be very small (< 10 edges over 5 seconds)
            assert abs(result['drift']) < 10, \
                f"Baseline drift too large: {result['drift']}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
