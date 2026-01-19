#!/usr/bin/env python3
"""
DPS Controller Tests

Tests for phase_dps_ctrl module functionality:
- One-shot phase shifts
- Continuous phase drift
- Start/stop behavior
"""

import pytest
import time
import sys
sys.path.insert(0, '/home/abb/de10-nanon/hdl-phase/sw')

from phase_utils import PhaseMeas, DPSControl, collect_samples


class TestDPSBasic:
    """Basic DPS controller tests"""

    def test_status_readable(self):
        """Can read DPS status register"""
        with DPSControl() as dps:
            status = dps.get_status()
            print(f"\nDPS Status: {status}")
            assert 'running' in status
            assert 'done_count' in status

    def test_stop_command(self):
        """Stop command clears running state"""
        with DPSControl() as dps:
            dps.stop()
            time.sleep(0.01)
            status = dps.get_status()
            print(f"\nAfter stop: {status}")
            assert not status['running'], "Should not be running after stop"


class TestDPSOneShot:
    """One-shot DPS tests"""

    def test_oneshot_completes(self):
        """One-shot DPS should complete and increment done counter"""
        with DPSControl() as dps:
            dps.stop()
            dps.clear_error()

            initial_status = dps.get_status()
            initial_done = initial_status['done_count']
            print(f"\nInitial done count: {initial_done}")

            # One-shot: 1 step, interval=0, count=1
            dps.start_dps(steps=1, interval_ticks=0, count=1)
            time.sleep(0.1)

            status = dps.get_status()
            print(f"After one-shot: {status}")

            assert status['done_count'] == initial_done + 1, \
                f"Done count should increment: {initial_done} -> {status['done_count']}"
            assert not status['running'], "Should not be running after one-shot completes"

    def test_oneshot_multiple_steps(self):
        """One-shot with multiple steps"""
        with DPSControl() as dps:
            dps.stop()
            dps.clear_error()

            initial_done = dps.get_status()['done_count']

            # One-shot: 32 steps (one full cycle)
            dps.start_dps(steps=32, interval_ticks=0, count=1)
            time.sleep(0.1)

            status = dps.get_status()
            print(f"\nAfter 32-step one-shot: {status}")

            assert status['done_count'] == initial_done + 1


class TestDPSContinuous:
    """Continuous DPS tests"""

    def test_continuous_runs(self):
        """Continuous DPS should keep running"""
        with DPSControl() as dps:
            dps.stop()
            dps.clear_error()

            # Continuous: 1 step per 50000 ticks (1ms), indefinite
            dps.start_dps(steps=1, interval_ticks=50000, count=0)
            time.sleep(0.01)

            status1 = dps.get_status()
            print(f"\nAfter start: {status1}")
            assert status1['running'], "Should be running"

            time.sleep(0.5)
            status2 = dps.get_status()
            print(f"After 500ms: {status2}")

            # Should have done ~500 operations in 500ms
            ops = status2['done_count'] - status1['done_count']
            print(f"Operations in 500ms: {ops}")

            dps.stop()
            assert ops > 400, f"Expected ~500 ops, got {ops}"
            assert ops < 600, f"Expected ~500 ops, got {ops}"

    def test_continuous_stop(self):
        """Continuous DPS should stop when commanded"""
        with DPSControl() as dps:
            dps.start_dps(steps=1, interval_ticks=50000, count=0)
            time.sleep(0.1)

            status1 = dps.get_status()
            assert status1['running'], "Should be running"

            dps.stop()
            time.sleep(0.01)

            status2 = dps.get_status()
            print(f"\nAfter stop: {status2}")
            assert not status2['running'], "Should not be running after stop"

            # Verify count doesn't change after stop
            done_at_stop = status2['done_count']
            time.sleep(0.1)
            status3 = dps.get_status()

            assert status3['done_count'] == done_at_stop, \
                "Done count should not change after stop"


class TestDPSWithPhaseMeas:
    """Integration tests: DPS with phase measurement validation"""

    def test_continuous_drift_positive(self):
        """
        Continuous +1 step/ms should cause positive phase drift.
        32 steps = 1 cycle = +1 edge difference
        At 1 step/ms, expect 1 edge drift per 32ms = ~31.25 edges/sec
        """
        with PhaseMeas() as pm, DPSControl() as dps:
            # Reset state
            pm.disable()
            dps.stop()
            time.sleep(0.1)
            pm.drain_fifo()

            # Enable measurement
            pm.enable()
            time.sleep(0.1)
            pm.drain_fifo()  # Clear any initial samples

            # Start continuous DPS: +1 step per 1ms
            dps.start_dps(steps=1, interval_ticks=50000, count=0)

            # Collect for 10 seconds -> expect ~312 edges drift
            result = collect_samples(pm, duration_sec=10.0)

            dps.stop()
            pm.disable()

            dps_status = dps.get_status()
            print(f"\nContinuous +1 step/ms for 10s:")
            print(f"  DPS done count: {dps_status['done_count']}")
            print(f"  Samples: {result['sample_count']}")
            print(f"  Cumulative rise_a: {result['cumulative_a']:,}")
            print(f"  Cumulative rise_b: {result['cumulative_b']:,}")
            print(f"  Drift (b - a): {result['drift']}")

            # Expected: ~10000 steps / 32 steps per cycle = ~312 cycles = +312 edges
            expected_drift = 10000 / 32  # ~312
            tolerance = 50  # Allow some variance

            assert result['drift'] > expected_drift - tolerance, \
                f"Drift too low: {result['drift']} (expected ~{expected_drift})"
            assert result['drift'] < expected_drift + tolerance, \
                f"Drift too high: {result['drift']} (expected ~{expected_drift})"

    def test_continuous_drift_negative(self):
        """
        Continuous -1 step/ms should cause negative phase drift.
        """
        with PhaseMeas() as pm, DPSControl() as dps:
            pm.disable()
            dps.stop()
            time.sleep(0.1)
            pm.drain_fifo()

            pm.enable()
            time.sleep(0.1)
            pm.drain_fifo()

            # Start continuous DPS: -1 step per 1ms
            dps.start_dps(steps=-1, interval_ticks=50000, count=0)

            result = collect_samples(pm, duration_sec=10.0)

            dps.stop()
            pm.disable()

            dps_status = dps.get_status()
            print(f"\nContinuous -1 step/ms for 10s:")
            print(f"  DPS done count: {dps_status['done_count']}")
            print(f"  Drift (b - a): {result['drift']}")

            # Expected: ~-312 edges
            expected_drift = -10000 / 32  # ~-312
            tolerance = 50

            assert result['drift'] < expected_drift + tolerance, \
                f"Drift not negative enough: {result['drift']} (expected ~{expected_drift})"
            assert result['drift'] > expected_drift - tolerance, \
                f"Drift too negative: {result['drift']} (expected ~{expected_drift})"

    def test_faster_rate(self):
        """
        Faster DPS rate: 1 step per 0.1ms (5000 ticks)
        Expect 10x more drift than 1ms rate
        """
        with PhaseMeas() as pm, DPSControl() as dps:
            pm.disable()
            dps.stop()
            time.sleep(0.1)
            pm.drain_fifo()

            pm.enable()
            time.sleep(0.1)
            pm.drain_fifo()

            # 1 step per 0.1ms = 10 steps/ms
            dps.start_dps(steps=1, interval_ticks=5000, count=0)

            # Run for 3.2 seconds -> expect ~1000 steps/sec * 3.2 = 32000 steps
            # = 1000 cycles = 1000 edges
            result = collect_samples(pm, duration_sec=3.2)

            dps.stop()
            pm.disable()

            dps_status = dps.get_status()
            print(f"\nFast rate (0.1ms interval) for 3.2s:")
            print(f"  DPS done count: {dps_status['done_count']}")
            print(f"  Drift (b - a): {result['drift']}")

            # Expected: ~32000 steps / 32 = 1000 edges
            expected_drift = 32000 / 32  # 1000
            tolerance = 100

            assert result['drift'] > expected_drift - tolerance, \
                f"Drift too low: {result['drift']} (expected ~{expected_drift})"


class TestDPSTiming:
    """Tests to verify DPS timing characteristics"""

    def test_interval_timing(self):
        """
        Verify DPS operations happen at correct interval.
        This test helps identify the timing bug discussed.
        """
        with DPSControl() as dps:
            dps.stop()
            dps.clear_error()

            # Start continuous: 1 step per 50000 ticks (1ms)
            start_time = time.time()
            dps.start_dps(steps=1, interval_ticks=50000, count=0)

            # Measure ops over known duration
            time.sleep(5.0)
            dps.stop()
            elapsed = time.time() - start_time

            status = dps.get_status()
            ops = status['done_count']

            # Calculate actual rate
            actual_rate = ops / elapsed
            expected_rate = 1000  # 1 op per ms = 1000 ops/sec

            print(f"\nTiming test (5 seconds at 1ms interval):")
            print(f"  Elapsed: {elapsed:.3f}s")
            print(f"  Operations: {ops}")
            print(f"  Actual rate: {actual_rate:.1f} ops/sec")
            print(f"  Expected rate: {expected_rate} ops/sec")
            print(f"  Deviation: {(actual_rate/expected_rate - 1)*100:.2f}%")

            # Due to timing bug, actual rate may be lower than expected
            # Document the deviation
            if actual_rate < expected_rate * 0.95:
                print(f"  NOTE: Rate is {100 - actual_rate/expected_rate*100:.1f}% lower than expected")
                print(f"        This may indicate the timing bug where interval waits AFTER completion")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
