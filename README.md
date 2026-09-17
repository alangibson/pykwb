# pykwb
Library to interpret the serial output of a KWB Comfort 3 controller. Commonly used on Easy Fire heaters.

## Quick Start

From the repository root:

```sh
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install .
```

Run with your RS485 terminal server's host and port:

```sh
python3 -m pykwb.kwb --tcp --host 192.168.1.100 --port 23 --summary
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

## Development

### Testing

```sh
python3 -m unittest discover -s tests -v
```

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
