# pykwb
Library to interpret the serial output of a KWB Easyfire Pellet Central Heating Unit

Setup

python3 setup.py build

python3 setup.py install

or

pip3 install pykwb

Works over serial or via a RS485 terminal server (telnet)

## Parameters

### Menu

Betriebzustand
    Kessel
        Breit (+Anf)
            Kesselleistung:     0%              ('u', 13, 1, 1, '%')
            Kesseltemp. Ist:    55 C
            Kesselt. Soll:      60 C
            Kesselpumpe:        100%
        Rucklauftemp.:
            RLT.soll/ist:       45/57 C         
            RLA Ventil          Aus
            Volllaststd.        12043 h
            Verbrauch:          11.839 t
    Heizkreise
        Heizkreis 0
        Heizkreis 1
            Raumtemp. Soll:     8 C
            Aussentemperatur:   14 C            ('s', 18, 2, 0.1, '°C')
            Vorlauf. Ist        30 C
            Vorlauf Soll        20 C
            Steigung:           0.60
            Raumeinfluss:       0%
            Pumpe:              Aus
            Mischer:            Aus
            Wahlschalter:       fehlt
        Heizkreis 3
            Raumtemp. Soll:     19 C
            Aussentemperatur:   14 C
            Vorlauf. Ist        25 C
            Vorlauf Soll        23 C
            Steigung:           0.70
            Raumeinfluss:       0%
            Pumpe:              Ein
            Mischer:            Aus
            Wahlschalter:       fehlt
        Heizkreis 4
            Raumtemp. Ist:      24 C
            Raumtemp. Soll:     22 C
            Aussentemperatur:   14 C
            Vorlauf. Ist        28 C
            Vorlauf Soll        28 C
            Steigung:           0.65
            Raumeinfluss:       0%
            Pumpe:              Ein
            Mischer:            Aus
            Wahlschalter:       fehlt
    Boiler
        Boiler 0
            Isttemperatur.      44 C            ('s', 12, 2, 0.1, '°C')
            Solltemperatur.     50 C
            Pumpe               Aus
            Anforderung         Aus
        Boiler 1
    Puffer
        Puffer 0
            Temperatur          50 C
            Temperatur Soll     28 C
            Anforderung         Ein
        Puffer 1
            Temperatur          47 C
            Temperatur Soll     20 C
            Pumpe               Aus
            Anforderung         Aus
    Raumaustragung
        Raumaustragung          Aus
        Saugturbine             Aus
        ueberfuellschutz        Ein
        Reststunden             8 h
        Schneckenantrieb        Aus
        Temp. Antrieb           Ein
        Tueb Brennstoff         Ein
    Zweitkessel
    Leistungsmessung
    KHM Zweitkessel

## References

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

- Serial protocol analysis from Dirk Abel
https://www.mikrocontroller.net/attachment/353784/KWB_RS485_Protokoll.pdf

https://github.com/windundsterne/esp-kwb-mqttlogger/blob/main/esp-kwb-mqttlogger.ino