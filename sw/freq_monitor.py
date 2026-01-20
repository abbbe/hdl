#!/usr/bin/env python3
"""
Frequency Monitor for Phase Measurement System

Continuously displays:
- Measured frequency from raw debug counters (bypasses FIFO bug)
- FIFO sample statistics
- Drift between channels A and B in PPM

Usage:
  sudo python3 freq_monitor.py           # Update every 1 second
  sudo python3 freq_monitor.py --fast    # Update every 0.5 second
  sudo python3 freq_monitor.py -i 2      # Update every 2 seconds
"""

import sys
import time
import argparse

sys.path.insert(0, '/home/abb/de10-nanon/hdl-phase/sw')
from phase_utils import PhaseMeas


def handle_wrap(curr, prev):
    """Handle 32-bit counter wrap"""
    if curr < prev:
        # Counter wrapped
        return (0x100000000 - prev) + curr
    return curr - prev


def format_freq(hz):
    """Format frequency with appropriate unit"""
    if hz >= 1e9:
        return f"{hz/1e9:.6f} GHz"
    elif hz >= 1e6:
        return f"{hz/1e6:.6f} MHz"
    elif hz >= 1e3:
        return f"{hz/1e3:.3f} kHz"
    else:
        return f"{hz:.1f} Hz"


def main():
    parser = argparse.ArgumentParser(description="Frequency monitor for phase measurement")
    parser.add_argument("-i", "--interval", type=float, default=1.0,
                        help="Update interval in seconds (default: 1.0)")
    parser.add_argument("--fast", action="store_true",
                        help="Fast mode: 0.5 second updates")
    args = parser.parse_args()

    interval = 0.5 if args.fast else args.interval

    print("Frequency Monitor")
    print("=" * 70)
    print("Press Ctrl+C to exit")
    print()

    with PhaseMeas() as pm:
        pm.enable()

        # Initial readings
        prev_counters = pm.read_debug_counters()
        prev_time = time.time()

        # Cumulative drift tracking
        cumul_a = 0
        cumul_b = 0
        start_time = prev_time

        # FIFO tracking
        fifo_samples = 0
        fifo_sum_a = 0
        fifo_sum_b = 0

        try:
            while True:
                time.sleep(interval)

                # Read current state
                curr_time = time.time()
                curr_counters = pm.read_debug_counters()
                status = pm.get_status()

                # Calculate deltas with wrap handling
                dt = curr_time - prev_time
                delta_a = handle_wrap(curr_counters['rise_a'], prev_counters['rise_a'])
                delta_b = handle_wrap(curr_counters['rise_b'], prev_counters['rise_b'])

                # Update cumulative
                cumul_a += delta_a
                cumul_b += delta_b
                total_time = curr_time - start_time

                # Calculate frequencies
                freq_a = delta_a / dt
                freq_b = delta_b / dt

                # Calculate PPM difference (B relative to A)
                if freq_a > 0:
                    ppm_diff = ((freq_b - freq_a) / freq_a) * 1e6
                else:
                    ppm_diff = 0

                # Cumulative drift
                cumul_drift = cumul_b - cumul_a
                if cumul_a > 0:
                    cumul_ppm = (cumul_drift / cumul_a) * 1e6
                else:
                    cumul_ppm = 0

                # Drain FIFO and accumulate
                batch_a = 0
                batch_b = 0
                batch_count = 0
                while True:
                    s = pm.read_fifo()
                    if s is None:
                        break
                    _, rise_a, _, rise_b, _ = s
                    batch_a += rise_a
                    batch_b += rise_b
                    batch_count += 1

                fifo_samples += batch_count
                fifo_sum_a += batch_a
                fifo_sum_b += batch_b
                fifo_drift = fifo_sum_b - fifo_sum_a

                # Display
                print(f"\033[2J\033[H", end="")  # Clear screen
                print("Frequency Monitor")
                print("=" * 70)
                print()
                print("RAW COUNTERS (accurate, bypasses FIFO bug):")
                print(f"  Channel A: {format_freq(freq_a):>20}")
                print(f"  Channel B: {format_freq(freq_b):>20}")
                print(f"  Instant PPM (B-A): {ppm_diff:+.3f}")
                print()
                print(f"CUMULATIVE ({total_time:.1f}s):")
                print(f"  Edges A: {cumul_a:>15,}")
                print(f"  Edges B: {cumul_b:>15,}")
                print(f"  Drift:   {cumul_drift:>+15,} edges")
                print(f"  PPM:     {cumul_ppm:>+15.3f}")
                print()
                print(f"FIFO (affected by double-pop bug - shows ~half):")
                print(f"  Samples:  {fifo_samples:>10}")
                print(f"  Sum A:    {fifo_sum_a:>15,}")
                print(f"  Sum B:    {fifo_sum_b:>15,}")
                print(f"  Drift:    {fifo_drift:>+15,}")
                print(f"  Status:   count={status['fifo_count']}, overflow={status['overflow']}")
                print()
                print("-" * 70)
                print("Press Ctrl+C to exit")

                # Update previous
                prev_counters = curr_counters
                prev_time = curr_time

        except KeyboardInterrupt:
            print("\n\nStopped.")
            pm.disable()

            # Final summary
            print("\nFinal Summary:")
            print(f"  Duration: {total_time:.1f} seconds")
            print(f"  Avg Freq A: {format_freq(cumul_a / total_time)}")
            print(f"  Avg Freq B: {format_freq(cumul_b / total_time)}")
            print(f"  Total Drift: {cumul_drift:+,} edges ({cumul_ppm:+.3f} ppm)")


if __name__ == "__main__":
    main()
