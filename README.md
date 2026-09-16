# pykwb
Library to interpret the serial output of a KWB Easyfire Pellet Central Heating Unit

Setup

python3 setup.py build

python3 setup.py install

or

pip3 install pykwb

Works over serial or via a RS485 terminal server (telnet)

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