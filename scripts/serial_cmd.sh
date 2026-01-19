#!/bin/bash
# Send command to serial port and capture response
# Usage: serial_cmd.sh "command" [port] [baud] [timeout_seconds]

CMD=${1:-""}
PORT=${2:-/dev/ttyUSB0}
BAUD=${3:-115200}
TIMEOUT=${4:-3}

# Configure serial port
stty -F "$PORT" "$BAUD" cs8 -cstopb -parenb raw -echo

# Send command if provided
if [ -n "$CMD" ]; then
    echo -e "$CMD\r" > "$PORT"
fi

# Read response with timeout
timeout "$TIMEOUT" dd if="$PORT" bs=1 count=4096 2>/dev/null

exit 0
