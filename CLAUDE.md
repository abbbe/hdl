# Clock Measurement Test System

I am developing components for clock phase monitoring system including its testbed.

Its core is DE10-NANO development board (FPGA + HPS), which will host all elements of the testbed.

See TECHNICAL.md for more details.

The FPGA building blocks:

* Internal 100MHz measurement clock
* Integer-n PLL clock generator, with DPS tuning
* Meassurement module, for now just push edge counts into FIFO every 500us
* Memory-mapped registers and FIFO interfaces with HPS Linux

In the testbed generator output will be exposed on GPIO and tied to clock edge counter.

Linux tools:

* Generator control tool, to control and monitor the generator
* Measurement control tool, to control measurement module, stream data
* Test suite
  * One shot test tool
    * Receives generator configuration
    * Receives expected measurement outcomes with tolerances, logs it
    * Runs the test, analyses the results, makes PASS or FAIL decision
  * Batch test tool
    * Receives a list of test specification,
    * Runs them all (optionally in an indefinite loop),
    * Display the results to the console, including accumulated PASS FAIL counts

## Testbed

The testbed consists of:
- This Linux host (Altera Lite 24.1 under /opt/altera_lite/24.1std/)
- DE10-Nano (Cyclone V SoC - 5CSEBA6U23I7), connected to Linux
  - USB serial (/dev/ttyUSB0 115200 baud)
  - Network (use `ssh analog@analog.local` to SSH into HPS Linux)
  - USB Blaster (can be used with SignalTap)

## Development process

Develop iteratively until objectives are reached. If objectives of the current iteration are not clear - ask to confirm the objectives.
Develop test scripts and FPGA code, build FPGA bitstream, upload it into FPGA.
Run tests, analyse results.
Rinse and repeat.

Use all tools and connectivity options at your disposal to recover the system if something is not working.