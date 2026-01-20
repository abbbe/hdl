#!/usr/bin/env python3
"""
Diagnostic: FIFO double-pop bug test

Tests whether the FIFO read pointer increments by 1 or 2 per read.
Expected: count decrements by 1 per read
Bug: count decrements by 2 per read

Usage: sudo python3 diag_fifo_pop.py
"""

import sys
import time
sys.path.insert(0, '/home/abb/de10-nanon/hdl-phase/sw')
from phase_utils import PhaseMeas


def main():
    print("FIFO Double-Pop Bug Diagnostic")
    print("=" * 50)

    with PhaseMeas() as pm:
        # Setup: clear FIFO and generate samples
        pm.disable()
        pm.drain_fifo()
        time.sleep(0.1)

        pm.enable()
        time.sleep(0.01)  # ~20 samples at 2kHz
        pm.disable()
        time.sleep(0.1)

        # Check initial state
        status = pm.get_status()
        initial_count = status['fifo_count']
        print(f"\nInitial FIFO count: {initial_count}")
        print(f"Expected if full: 16")

        # Read samples and track count changes
        print("\nReading samples (watching count decrement):")
        print("-" * 50)

        reads = 0
        prev_count = initial_count

        for i in range(20):
            status = pm.read32(0x04)
            count = status & 0x1F
            empty = bool(status & 0x40)

            if empty:
                print(f"  Read {i}: EMPTY")
                break

            # Read DATA5 to trigger pop
            pm.read32(0x1C)
            reads += 1

            decrement = prev_count - count if i > 0 else 0
            print(f"  Read {i}: count={count:2d}  (decremented by {decrement})")
            prev_count = count

        print("-" * 50)
        print(f"\nTotal reads before empty: {reads}")
        print(f"Initial count was: {initial_count}")

        if initial_count > 0:
            ratio = initial_count / reads if reads > 0 else 0
            print(f"Ratio (count/reads): {ratio:.1f}")

            if abs(ratio - 2.0) < 0.1:
                print("\nBUG CONFIRMED: Pointer increments by 2 per read")
                return 1
            elif abs(ratio - 1.0) < 0.1:
                print("\nOK: Pointer increments by 1 per read")
                return 0
            else:
                print(f"\nUNEXPECTED: Ratio is {ratio:.1f}")
                return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
