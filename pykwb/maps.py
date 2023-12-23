
# SIGNAL_MAPS = [{} for i in range(255)]

# # Sense message
# # 16: Sense message from the boiler (to the control panel)
# SIGNAL_MAPS[16] = {
#     # Name: Type='b'(bit), Offset, Bit
#     # Name: Type='s'(signed)/'u'(unsigned), Offset, Length, Factor, Unit
#     'T_Vorlauf_HK1': ('s', 5, 2, 0.1, '°C'),
#     'T_Ruecklauf_Kessel': ('s', 7, 2, 0.1, '°C'),
#     'T_Boiler': ('s', 9, 2, 0.1, '°C'),
#     'T_Kessel':  ('s', 11, 2, 0.1, '°C'),
#     'T_Buffer_Bottom': ('s', 13, 2, 0.1, '°C'),
#     'T_Buffer_Oben':  ('s', 15, 2, 0.1, '°C'),
#     'T_Outside': ('s', 17, 2, 0.1, '°C'),
#     'T_flue gas': ('s', 19, 2, 0.1, '°C'),
#     'T_Stokerkanal': ('s', 29, 2, 0.1, '°C')
# }

# # Control message
# # 17: Control message from control panel to boiler
# SIGNAL_MAPS[17] = {
#     'Brandschutzklappe':    ('b', 1, 1),
#     'Alarm 2':              ('b', 1, 2),
#     'Alarm 1':              ('b', 1, 3),
#     'Leistungsausgang':     ('b', 1, 4),
#     'Tank 0 Pumping':       ('b', 1, 5),
#     'Loop 2 Pumping':       ('b', 1, 6),
#     'Loop 1 Pumping':       ('b', 1, 7),
#     'Ash removal':              ('b', 2, 0),
#     'cleaning':                 ('b', 2, 1),
#     'RL_Mischer ein':           ('b', 2, 2),
#     'RL_Mischer 0-auf|1-zu':    ('b', 2, 3),
#     'HK2_Mixer':                ('b', 2, 4),
#     'HK2_Mischer 0-auf|1-zu':   ('b', 2, 5),
#     'HK1_Mixer':                ('b', 2, 6),
#     'Zündung':              ('b', 3, 0),
#     'main relay':           ('b', 3, 4),
#     'Raumaustragung':       ('b', 3, 6),
#     'Rücklaufpumpe':        ('u', 4, 1, 0.3921, '%'),
#     'Gebläsestufe':         ('u', 5, 1, 0.1960, 'Stufe'),
#     'Saugzugstufe':         ('u', 6, 1, 0.1960, 'Stufe'),
#     'Kessel_AN':            ('b', 15, 0),
# }

# #
# # Electrische Anschluesse (ELS TYU HKM-XLa)
# #
# # Messages observed with KWB Comfort 3 in a KWB Easyfire 1
# #

# # Sense message
# SIGNAL_MAPS[32] = {
#     'Ash Can OK':               ('b', 3, 6), # de=Aschebehaelter
#     'Heater Running':           ('b', 3, 7), # Hauptantriebimpuls =  Hauptantrieb läuft und produziert Impulse
#     'Clean Out Alarm':          ('b', 4, 1), # de=Klixon Raumaustragung
#     'Ash Grate Full':           ('b', 4, 2), # de=Füllstandssensor
#     'Igniter Alarm':            ('b', 4, 3), # de=Klixon Stoker
#                                              # OR de=Pellet_Vorrat
#     'Endschalter BS Klappe':    ('b', 4, 4), # de=Endschalter BS Klappe
#     'Door Contact':             ('b', 4, 5), # de=Türkontakt; Not sure if this is real
#     'Extern 2':                 ('b', 4, 6), # not sure if this is real
#     'Extern 1':                 ('b', 4, 7),
#     'Safety Thermostat':        ('b', 5, 0), # de=Sicherheitsthermostat
#     'RFK Taste':                ('b', 5, 1),
#     'TÜB Stoker':               ('b', 5, 2),
#     # 'RFK Taste':              ('b', 5, 2),
#     'Loop 1 Out Temp':          ('s', 6, 2, 0.1, '°C'),     # de=HK1 Vorlauf Temperatur
#     'Heater Return Temp':       ('s', 8, 2, 0.1, '°C'),     # de=Rücklauf Temperatur
#     'Tank 0 Temp':              ('s', 10, 2, 0.1, '°C'),    # de=Boiler 0 Temperatur
#     'Heater Temp':              ('s', 12, 2, 0.1, '°C'),    # de=Kessel Temperatur
#     'Buffer 1 Temp':            ('s', 14, 2, 0.1, '°C'),    # de=Puffer 2 (unten) Temperatur
#     'Buffer 2 Temp':            ('s', 16, 2, 0.1, '°C'),    # de=Puffer 1 (oben) Temperatur
#     'Outside Temp':             ('s', 18, 2, 0.1, '°C'),    # de=Außen Temperatur
#     'Exhaust Temp':             ('s', 20, 2, 0.1, '°C'),    # de=Rauchgastemperatur
#     'CPU Temp':                 ('s', 22, 2, 0.1, '°C'),    # de=Proztemperatur
#     # Always 50C
#     # 'Loop 1 Remote Adjustment Temp':    ('s', 24, 2, 0.1, '°C'),    # de=HK1 Fernverstellung Temperatur
#     # Always 50C
#     # 'Loop 2 Remote Adjustment Temp':    ('s', 26, 2, 0.1, '°C'),    # de=HK2 Fernverstellung Temperatur
#     'Loop 2 Out Temp':          ('s', 28, 2, 0.1, '°C'),
#     'Photodiode':               ('s', 32, 2, 0.1, ''),
#     'Pressure':                 ('s', 34, 2, 0.001, 'mBar'),
#     'Suction Speed':            ('u', 69, 2, 0.6, 'rpm'),   # de=Drehzahl_Saugzug
#     'Fan Speed':                ('u', 71, 2, 0.6, 'rpm'),   # de=Geblaese OR Drehzahl_Luefter
# }

# # Control message
# SIGNAL_MAPS[33] = {
#     #
#     # espinclude.h functions
#     #   double getval2(unsigned char *anData, int nOffset, int nLen, double fFactor, int bSigned)
#     #   int getbit(unsigned char *data, int nOffset, int nBit)
#     #
#     'Heater Power On':              ('b', 1, 2),
#     'Loop 1 Pumping':               ('b', 1, 5),
#     'Loop 1 Mixer Opened':          ('b', 1, 7),
#     'Loop 1 Mixer Closed':          ('b', 2, 0),
#     'RLA Valve State':              ('b', 2, 3),
#     'Tank 0 Pumping':               ('b', 2, 5),
#     'Buffer Pumping':               ('b', 2, 7),
#     'No Interference State':        ('b', 3, 0),    #de=Keine_Stoerung
#     'Ignition State':               ('b', 3, 2),
#     'Ash Grate Revolving':          ('b', 3, 6),    # de=Drehrost
#     'Cleaning State':               ('b', 3, 7),    # de=Reinigung
#     'Ash Clearing Saugturbine':     ('b', 4, 1),    # de=Raumaustragung Saugturbine
#     'Sunction':                     ('b', 4, 5),    # de=Saugzug
#     'Heater Active':                ('b', 5, 0),    # de=Hauptantrieb
#     'Buffer 0 Pumping':             ('u', 8, 1, 100.0/255.0, '%'),  # de=pumpe_puffer
#     'Heater Main Contact On':       ('b', 9, 1),                    # de=Heater Hauptschuetz
#     'Ash Clearing':                 ('b', 9, 2),                    # de=Raumaustragung
#     'Main Drive Cycle Time':        ('u', 10, 2, 10, 'msec'),       # de=Hauptantriebtakt == Taktzeit in millisekunden
#     'Main Drive Time':              ('u', 12, 2, 10, 'msec'),       # Hauptantrieb == HAMotor Laufzeit in Millisekunden
#     'Heater Output':                ('u', 13, 1, 1, '%'),           # de=Kesselleistung
#     'Ignition':                     ('b', 16, 2),                   # de=Zuendung
# }

# #
# # Steckmodul 1 fuer HK0 and Zweitkessel (EBAA1021)
# #

# # Sense message
# SIGNAL_MAPS[48] = {
#     # Name: Type='b'(bit), Offset, Bit
#     # Name: Type='s'(signed)/'u'(unsigned), Offset, Length, Factor, Unit
#     # 'T_Vorlauf_HK1': ('s',5, 2, 0.1,'C'),
#     'T_Vorlauf_HK0': ('s', 45, 2, 0.1, '°C'),
#     'T_Ruecklauf_Kessel': ('s', 7, 2, 0.1, '°C'),
#     'T_Boiler': ('s', 9, 2, 0.1, 'Â°C'),
#     'T_Kessel': ('s', 11, 2, 0.1, 'Â°C'),
#     'T_Buffer_Bottom': ('s', 13, 2, 0.1, 'Â°C'),
#     'T_Buffer_Mitte': ('s', 29, 2, 0.1, 'Â°C'),
#     'T_Buffer_Oben': ('s', 15, 2, 0.1, 'Â°C'),
#     'T_flue gas': ('s', 39, 2, 0.1, 'Â°C'),
#     'T_Aussen': ('s', 41, 2, 0.1, 'Â°C'),
#     'T_room_temp._actual': ('s', 43, 2, 0.1, 'Â°C'),
#     'T_room_temp._setpoint': ('s', 49, 2, 0.1, 'Â°C'),
#     'oxygen': ('s', 31, 2, 0.1, '%')
# }

# # Control message
# SIGNAL_MAPS[49] = {
#     'Boiler_mainrelay':     ('b', 1, 3),
#     'Boiler Pumping':       ('b', 1, 5),
#     'Loop 0 Pumping':       ('b', 3, 9),
#     'Loop 0 Mixer Open':    ('b', 3, 5),
#     'Loop 0 Mixer Closed':  ('b', 3, 6)
# }

# #
# # Steckmodul for HK3/HK4 and HK3/6?
# # TODO what card is this?
# # 
# # Messages observed with KWB Comfort 3 in a KWB Easyfire 1
# #

# # Sense message
# # 64: Response from the heating circuit controller to the control panel
# #
# # TODO what does this note mean? "In the odd counters HK 4/3 and in the straight HK 6/3"
# #
# SIGNAL_MAPS[64] = {
#     'Loop 4 Out Temp':          ('s', 19, 2, 0.1, '°C'),
#     'Loop 3 Out Temp':          ('s', 21, 2, 0.1, '°C'),
# }

# # Control message
# # 65: Message from control panel to heating circuit controller
# SIGNAL_MAPS[65] = {
# }
