#!/bin/bash
# Serial port reader for DE10-Nano debugging
# Usage: serial_read.sh [port] [baud] [timeout_seconds]

PORT=${1:-/dev/ttyUSB0}
BAUD=${2:-115200}
TIMEOUT=${3:-5}

# Configure serial port
stty -F "$PORT" "$BAUD" cs8 -cstopb -parenb raw -echo

# Read with timeout, capture whatever comes
timeout "$TIMEOUT" dd if="$PORT" bs=1 count=4096 2>/dev/null

exit 0
