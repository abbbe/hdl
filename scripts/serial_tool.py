#!/usr/bin/env python3
"""
Serial port tool for DE10-Nano debugging.
Uses pyserial with proper timeout handling.

Usage:
    serial_tool.py read [port] [baud] [timeout_sec]
    serial_tool.py cmd "command" [port] [baud] [timeout_sec]
"""

import sys
import serial
import time

def read_serial(port='/dev/ttyUSB0', baud=115200, timeout=5):
    """Read from serial port with timeout."""
    try:
        ser = serial.Serial(port, baud, timeout=0.5)
        ser.reset_input_buffer()

        output = b''
        end_time = time.time() + timeout

        while time.time() < end_time:
            chunk = ser.read(1024)
            if chunk:
                output += chunk
                sys.stdout.buffer.write(chunk)
                sys.stdout.buffer.flush()

        ser.close()
        return output
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return b''

def send_cmd(cmd, port='/dev/ttyUSB0', baud=115200, timeout=3):
    """Send command and read response."""
    try:
        ser = serial.Serial(port, baud, timeout=0.5)
        ser.reset_input_buffer()

        # Send command with CR
        if cmd:
            ser.write((cmd + '\r').encode())
        else:
            ser.write(b'\r')

        output = b''
        end_time = time.time() + timeout

        while time.time() < end_time:
            chunk = ser.read(1024)
            if chunk:
                output += chunk
                sys.stdout.buffer.write(chunk)
                sys.stdout.buffer.flush()

        ser.close()
        return output
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return b''

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    action = sys.argv[1]

    if action == 'read':
        port = sys.argv[2] if len(sys.argv) > 2 else '/dev/ttyUSB0'
        baud = int(sys.argv[3]) if len(sys.argv) > 3 else 115200
        timeout = float(sys.argv[4]) if len(sys.argv) > 4 else 5
        read_serial(port, baud, timeout)

    elif action == 'cmd':
        cmd = sys.argv[2] if len(sys.argv) > 2 else ''
        port = sys.argv[3] if len(sys.argv) > 3 else '/dev/ttyUSB0'
        baud = int(sys.argv[4]) if len(sys.argv) > 4 else 115200
        timeout = float(sys.argv[5]) if len(sys.argv) > 5 else 3
        send_cmd(cmd, port, baud, timeout)

    else:
        print(f"Unknown action: {action}")
        print(__doc__)
        sys.exit(1)
