# pykwb
Library to interpret the serial output of KWB Comfort 3 controllers.

Supports Easyfire 1 and Easyfire 2 heaters.

## Quick Start

Get the code

```sh
git clone https://github.com/alangibson/pykwb.git
cd pykwb
git checkout improvements
```

Then install:

```sh
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install .
```

Run with your RS485 terminal server's host and port:

```sh
python3 -m pykwb.kwb --tcp --host 127.0.0.1 --port 23 --summary
```

(Note: You will need a RS485 to network converter like this : https://www.amazon.de/dp/B0BGHVRMPJ)

Or use your serial device:

```sh
python3 -m pykwb.kwb --serial --interface /dev/ttyUSB0 --summary
```

## Running

### Install

#### From Source

```sh
python3 setup.py build
python3 setup.py install
```

#### From Pypi Repo

```sh
pip3 install pykwb
```

### Async API

Requires Python 3.9+. TCP and serial listening are asynchronous; connections open
when listening starts. Use `await kwb.listen_for(seconds=5)` or
`await kwb.listen_forever()`, and `await kwb.close()` when finished. See
[execution and migration](docs/execution.md) and [TCP reconnection](docs/connection.md).
The CLI always uses async listening; the former `--mode` option is removed.

### Logging

Add `--log-level debug` to a run command to change verbosity. Levels: `none`,
`error`, `warning` (or `warn`), `info` (default), `debug`, `trace`.
`--log false` disables logging regardless of the level; `--no-summary` disables sensor summaries separately.

## Development

### Testing

```sh
python3 -m unittest discover -s tests -v
```

## Bug Reports

To file a bug report, append `--log-level trace > trace.log` to the command you're using to run pykwb. For example

```sh
python3 pykwb/kwb.py --tcp --host 127.0.0.1 --port 23 --log-level trace > trace.log
```

Then [open an issue here](https://github.com/alangibson/pykwb/issues), answer the questions and attach trace.log.

## References

- KWB Kessel RS485 Protokoll
https://www.mikrocontroller.net/topic/274137

- C implementation from thomas_t33
https://www.mikrocontroller.net/attachment/190264/rs485kwb.c
https://www.mikrocontroller.net/attachment/190265/rs485kwb.h

- Python implementation from markus_h62
https://www.mikrocontroller.net/attachment/200110/grabserial.py

- Python implementation from haros
https://www.mikrocontroller.net/attachment/345168/grab32.py
or
https://www.mikrocontroller.net/attachment/345375/logkwb.py

- PHP implementation from ksau
https://www.mikrocontroller.net/attachment/200878/kwb_log.php

- Perl implementation from markus_h62
https://www.mikrocontroller.net/attachment/203419/00_KWB.pm

- https://github.com/windundsterne/esp-kwb-mqttlogger/blob/main/esp-kwb-mqttlogger.ino
