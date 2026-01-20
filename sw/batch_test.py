#!/usr/bin/env python3
"""
Batch Test Script for Phase Measurement System

Tests:
1. Baseline 40 MHz - verify edge counting accuracy
2. Positive drift (+10 ppm on PLL_B) - verify drift detection
3. Negative drift (-10 ppm on PLL_B) - verify drift detection

Usage:
  sudo python3 batch_test.py           # Run all tests
  sudo python3 batch_test.py --loop    # Run indefinitely
"""

import sys
import time
import argparse
from dataclasses import dataclass
from typing import Optional

sys.path.insert(0, '/home/abb/de10-nanon/hdl-phase/sw')
from phase_utils import PhaseMeas, DPSControl, collect_samples


@dataclass
class TestResult:
    name: str
    passed: bool
    expected: str
    actual: str
    message: str = ""


# Test parameters
CLOCK_FREQ_MHZ = 40.0
SAMPLE_WINDOW_US = 500
EXPECTED_EDGES_PER_SAMPLE = int(CLOCK_FREQ_MHZ * SAMPLE_WINDOW_US)  # 20000

# DPS parameters for ~10 ppm
# At 40 MHz output, VCO is ~800 MHz, step size = 1/8 * (1/800MHz) = 156.25 ps
# ppm = (steps/interval_sec) * step_size_ps * 1e-6
# For 10 ppm: steps/sec = 10 / (156.25 * 1e-6) = 64000
# At interval=50000 ticks (1ms): steps = 64
DPS_STEP_SIZE_PS = 156.25  # At 800 MHz VCO
DPS_STEPS_10PPM = 64
DPS_INTERVAL_TICKS = 50000  # 1ms at 50 MHz sys_clk
DPS_PPM_NOMINAL = 10.0


def run_test_baseline(pm: PhaseMeas, duration_sec: float = 5.0) -> TestResult:
    """Test 1: Baseline 40 MHz - both clocks identical, no DPS"""

    pm.disable()
    time.sleep(0.1)
    pm.drain_fifo()

    pm.enable()
    result = collect_samples(pm, duration_sec)
    pm.disable()

    samples = result['samples']
    if not samples:
        return TestResult(
            name="Baseline 40 MHz",
            passed=False,
            expected=f"{EXPECTED_EDGES_PER_SAMPLE} edges/sample",
            actual="No samples collected",
            message="FIFO empty - check hardware"
        )

    # Check edge counts per sample
    edge_errors = []
    for i, s in enumerate(samples):
        _, rise_a, fall_a, rise_b, fall_b = s
        if abs(rise_a - EXPECTED_EDGES_PER_SAMPLE) > 1:
            edge_errors.append(f"sample {i}: rise_a={rise_a}")
        if abs(rise_b - EXPECTED_EDGES_PER_SAMPLE) > 1:
            edge_errors.append(f"sample {i}: rise_b={rise_b}")

    # Check cumulative drift
    drift = result['drift']
    drift_ok = abs(drift) < 10
    edges_ok = len(edge_errors) == 0

    passed = drift_ok and edges_ok

    avg_edges = sum(s[1] for s in samples) / len(samples)

    return TestResult(
        name="Baseline 40 MHz",
        passed=passed,
        expected=f"{EXPECTED_EDGES_PER_SAMPLE} edges/sample, drift < 10",
        actual=f"{avg_edges:.0f} edges/sample, drift = {drift}",
        message="" if passed else f"Edge errors: {edge_errors[:3]}..." if edge_errors else f"Drift too large: {drift}"
    )


def run_test_drift(pm: PhaseMeas, dps: DPSControl,
                   ppm: float, duration_sec: float = 10.0) -> TestResult:
    """Test with DPS-induced drift on PLL_B"""

    test_name = f"{'Positive' if ppm > 0 else 'Negative'} drift {ppm:+.0f}ppm"

    # Calculate DPS parameters
    steps = int(DPS_STEPS_10PPM * abs(ppm) / DPS_PPM_NOMINAL)
    if ppm < 0:
        steps = -steps

    # Expected drift: ppm * freq * time = edges
    # At 40 MHz, 10 ppm for 10 seconds = 10e-6 * 40e6 * 10 = 4000 edges
    expected_drift = int(ppm * 1e-6 * CLOCK_FREQ_MHZ * 1e6 * duration_sec)

    pm.disable()
    time.sleep(0.1)
    pm.drain_fifo()

    # Start DPS
    dps.stop()
    dps.clear_error()
    dps.start_dps(steps, DPS_INTERVAL_TICKS, 0)  # 0 = indefinite

    time.sleep(0.1)  # Let DPS stabilize

    pm.enable()
    result = collect_samples(pm, duration_sec)
    pm.disable()

    dps.stop()

    samples = result['samples']
    if not samples:
        return TestResult(
            name=test_name,
            passed=False,
            expected=f"{expected_drift:+d} edge drift",
            actual="No samples collected",
            message="FIFO empty - check hardware"
        )

    measured_drift = result['drift']

    # Check if drift is in correct direction and within 20% of expected
    correct_sign = (measured_drift * expected_drift) > 0 if expected_drift != 0 else True
    error_pct = abs(measured_drift - expected_drift) / abs(expected_drift) * 100 if expected_drift != 0 else 0

    passed = correct_sign and error_pct < 20

    return TestResult(
        name=test_name,
        passed=passed,
        expected=f"{expected_drift:+d} edge drift",
        actual=f"{measured_drift:+d} edge drift ({error_pct:.1f}% error)",
        message="" if passed else ("Wrong sign!" if not correct_sign else f"Error > 20%")
    )


def print_result(index: int, total: int, result: TestResult):
    """Print formatted test result"""
    status = "PASS" if result.passed else "FAIL"
    dots = "." * (40 - len(result.name))
    print(f"\n[{index}/{total}] {result.name} {dots} {status}")
    print(f"      Expected: {result.expected}")
    print(f"      Actual: {result.actual}")
    if result.message:
        print(f"      Note: {result.message}")


def run_all_tests(loop: bool = False):
    """Run all tests and print summary"""

    iteration = 0
    total_passed = 0
    total_failed = 0

    while True:
        iteration += 1

        print("=" * 60)
        print(f"Phase Measurement Batch Tests" + (f" (iteration {iteration})" if loop else ""))
        print("=" * 60)

        results = []

        with PhaseMeas() as pm:
            # Test 1: Baseline
            result = run_test_baseline(pm, duration_sec=5.0)
            results.append(result)
            print_result(1, 3, result)

            # Tests 2 & 3: Drift tests
            with DPSControl() as dps:
                # Test 2: Positive drift
                result = run_test_drift(pm, dps, ppm=+10.0, duration_sec=10.0)
                results.append(result)
                print_result(2, 3, result)

                # Test 3: Negative drift
                result = run_test_drift(pm, dps, ppm=-10.0, duration_sec=10.0)
                results.append(result)
                print_result(3, 3, result)

        passed = sum(1 for r in results if r.passed)
        failed = len(results) - passed
        total_passed += passed
        total_failed += failed

        print()
        print("=" * 60)
        print(f"SUMMARY: {passed}/{len(results)} tests passed")
        if loop:
            print(f"CUMULATIVE: {total_passed} passed, {total_failed} failed")
        print("=" * 60)

        if not loop:
            break

        print("\nStarting next iteration in 5 seconds... (Ctrl+C to stop)")
        time.sleep(5)

    return 0 if failed == 0 else 1


def main():
    parser = argparse.ArgumentParser(description="Batch test for phase measurement system")
    parser.add_argument("--loop", action="store_true", help="Run tests indefinitely")
    args = parser.parse_args()

    try:
        return run_all_tests(loop=args.loop)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        return 130


if __name__ == "__main__":
    sys.exit(main())
