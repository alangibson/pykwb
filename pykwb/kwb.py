# -*- coding: utf-8 -*-
"""
The MIT License (MIT)

Copyright (c) 2017 Markus Peter mpeter at emdev dot de

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.


Support for KWB central heating units.
"""

import logging
import csv
import os
import time
from datetime import datetime, timedelta
from pykwb.readers import SerialByteReader, TCPByteReader, FileByteReader

STATE_WAIT_FOR_HEADER = 1
STATE_READ_MSG = 2
MSG_TYPE_CTRL = 1
MSG_TYPE_SENSE = 2

PROP_LOGLEVEL_TRACE = 5
PROP_LOGLEVEL_DEBUG = 4
PROP_LOGLEVEL_INFO = 3
PROP_LOGLEVEL_WARN = 2
PROP_LOGLEVEL_ERROR = 1
PROP_LOGLEVEL_NONE = 0

PROP_MODE_SERIAL = 0
PROP_MODE_TCP = 1
PROP_MODE_FILE = 2

STATUS_WAITING = 0
STATUS_IS_PACKET = 1
STATUS_IS_SENSE_PACKET = 2
STATUS_SENSE_READ_PAYLOAD = 3
STATUS_SENSE_READ_MESSAGE_ID = 6
STATUS_SENSE_READ_COUNTER = 20
STATUS_SENSE_READ_PAYLOAD = 8
STATUS_SENSE_READ_CHECKSUM = 9
STATUS_IS_CTRL_PACKET = 10
STATUS_CTRL_READ_COUNTER = 11
STATUS_CTRL_READ_PAYLOAD = 12
STATUS_CTRL_READ_CHECKSUM = 19
STATUS_CTRL_READ_MESSAGE_ID = 21
STATUS_PACKET_DONE = 255

PROP_PACKET_SENSE = 0
PROP_PACKET_CTRL = 1

PROP_SENSOR_TEMPERATURE = 0
PROP_SENSOR_FLAG = 1
PROP_SENSOR_RAW = 2

TCP_IP = "127.0.0.1"
TCP_PORT = 23

SERIAL_INTERFACE = "/dev/ttyUSB0"
SERIAL_SPEED = 19200

_LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


def load_signal_maps(path='config/KWB Protocol - Messages.csv', source=10, message_ids=[32,33,64,65]):
    signal_maps = [{} for i in range(255)]
    filepath = os.path.join(os.path.dirname(__file__), path)
    with open(filepath, encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            row_message_id = int(row['message_id'])
            row_source = int(row['source'])
            row_key = row['key'] if row['key'] and row['key'] != '' else row['name_en'].lower().replace(' ', '_')
            if (row_source == source and row_message_id in message_ids):
                if row['type'] == 'bit':
                    sig = ('b', int(row['offset']), int(row['bit']), row_key, row['state_class'], row['device_class'])
                elif row['type'] == 'int':
                    sig = ('s' if int(row['signed']) else 'u', int(row['offset']), int(row['length']), float(row['scale']), row['units'], row_key, row['state_class'] ,row['device_class'] )
                else:
                    continue
                signal_maps[row_message_id][row_key] = sig
    return signal_maps


class KWBMessage:

    def __init__(self, message_id, length, counter, checksum, data: bytearray, message_type=0, timepoint=0, signal_map={}):
        self.timepoint = timepoint
        self.message_type = message_type
        self.length = length
        self.message_id = message_id
        self.counter = counter
        self.data = data
        self.checksum = checksum
        self.signal_map = signal_map

    def get_flag(self, offset, bit):
        """Get a boolean flag"""
        return (self.data[offset] >> bit) & 1

    def get_value(self, offset, length=2, factor=0.1, signed=False):
        """Get a numeric value"""
        value = 0
        # Accumulate value over all bytes
        for i in range(0, length):
            value += self.data[offset+i] << ((length-i-1) * 8)
        # Exclude disconnected analog sensors
        if value == 1300:
            return None
        # Adjust based on signedness
        if signed & (value > (1 << (length*8-1))):
            value -= (1 << (length*8))
        # Apply scaling factor
        value = value * factor
        return value

    def decode(self, signal_map=None):
        """Decode all values in message according to provided signal map"""
        signal_map = signal_map if signal_map else self.signal_map
        sensor_values = {}
        # Decode message according to the signal map
        for sensor_name, aSig in signal_map.items():
            if aSig[0] == 'b':
                # Name: Type, Offset, Bit
                value = self.get_flag(aSig[1], aSig[2])
                sensor_values[sensor_name] = (value, *aSig)
            else:
                # Name: Type, Offset, Length, Scale, Unit
                value = self.get_value(
                    aSig[1], aSig[2], aSig[3], aSig[0] == 's')
                sensor_values[sensor_name] = (value, *aSig)

        return sensor_values
    
    def dump(self):
        """Decode message as a table of values"""

        # TODO mbar values
        # TODO ms values
        # TODO rpm values

        # Decode data payload as if it was all flags
        flag_values = {}
        for offset in range(0, self.length - 6, 1):
            for bit in range(0, 8, 1):
                signal_name = ("flag_%02d_%02d" % (offset, bit))
                sig = (offset, bit)
                flag_values[signal_name] = ( self.get_flag(offset, bit), sig )

        # Decode data payload as if it was all temperatures
        temp_values, mbar_values, ms_values, rpm_values = {}, {}, {}, {}
        for offset in range(0, self.length - 6, 2):
            value = self.get_value(offset)
            temp_values["temp_%02d" % (offset,)] = ( value * 0.1 if value else value, (offset, 2, 0.1, '°C') )
            mbar_values["mbar_%02d" % (offset,)] = ( value * 0.001 if value else value, (offset, 2, 0.001, 'mbar') )
            ms_values["ms_%02d" % (offset,)] = ( value * 10 if value else value, (offset, 2, 10, 'ms') )
            rpm_values["rpm_%02d" % (offset,)] = ( value * 0.6 if value else value, (offset, 2, 0.6, 'rpm') )

        return {
            'flag': flag_values,
            'temp': temp_values,
            'mbar': mbar_values,
            'ms': ms_values,
            'rpm': rpm_values
        }

    def get_crc(self):
        def crc_add(crc, byte):
            crc = (((crc << 1) | crc >> 7) & 0xFF)
            crc += byte
            if (crc > 255):
                crc -= 255
            return crc
        crc = 0x02
        crc = crc_add(crc, self.length)
        crc = crc_add(crc, self.message_id)
        crc = crc_add(crc, self.counter)
        for i in range(len(self.data)):
            crc = crc_add(crc, self.data[i])
        return crc
    
    def is_crc_ok(self):
        """Returns true if message checksum is OK"""
        return self.get_crc() == self.checksum

    def copy_from(self, other_message):
        self.timepoint = other_message.timepoint
        self.message_type = other_message.message_type
        self.length = other_message.length
        self.message_id = other_message.message_id
        self.counter = other_message.counter
        self.data = other_message.data
        self.checksum = other_message.checksum

    def is_same(self, other_msg):
        return self.data == other_msg.data


class KWBSensor:
    """This Class represents as single sensor."""

    def __init__(self, _packet, _index, _name, _sensor_type):

        self._packet = _packet
        self._index = _index
        self._name = _name
        self._sensor_type = _sensor_type
        self._value = None
        self._available = False

    @property
    def index(self):
        """Returns the offset from the start of the packet."""
        return self._index

    @property
    def name(self):
        """Returns the name of the sensor."""
        return self._name

    @property
    def sensor_type(self):
        """Returns the type of the sensor. It can be CTRL or SENSE."""
        return self._sensor_type

    @property
    def unit_of_measurement(self):
        """Returns the unit of measurement of the sensor. It can be °C or empty."""
        if (self._sensor_type == PROP_SENSOR_TEMPERATURE):
            return "°C"
        else:
            return ""

    @property
    def value(self):
        """Returns the value of the sensor. Unit is unit_of_measurement."""
        return self._value

    @value.setter
    def value(self, _value):
        """Sets the value of the sensor. Unit is unit_of_measurement."""
        self._available = True
        self._value = _value

    @property
    def available(self):
        """Return if sensor is available."""
        return self._available

    def __str__(self):
        """Returns an informational text representation of the sensor."""
        return self.name + ": I: " + str(self.index) + " T: " + str(self.sensor_type) + "(" + str(self.unit_of_measurement) + ") V: " + str(self.value)


class KWBMessageStream:

    def __init__(self, reader: TCPByteReader, signal_maps, heater_config={}, reconnect=True, last_values={}):
        self.reader = reader
        self.state = STATE_WAIT_FOR_HEADER
        self.receive_finished = False
        # self.oMsg: KWBMessage = KWBMessage()
        self.signal_maps = signal_maps
        self.heater_config = heater_config
        self._reconnect = reconnect

        # State vars
        self.sTime = 0
        self.nType = 0
        self.nLen = 0
        self.nID = 0
        self.nCounter = 0
        self.anData = bytearray(0)
        self.nChecksum = 0
        self.oMsg = None
        self.last_timestamp_msec = last_values.get('last_timestamp', time.time_ns() / 1000000)
        self.run_time_sec = last_values.get('boiler_run_time', 0.0)
        self.energy_kWh = last_values.get('energy_output', 0.0)
        self.pellet_consumption_kg = last_values.get('pellet_consumption', 0.0)

    def _found_header(self):
        # header found
        self.state = STATE_READ_MSG
        # self.oMsg = KWBMessage()
        # self.oMsg.sTime = datetime.now()
        # # -> CtrlMessage
        # self.oMsg.nType = MSG_TYPE_CTRL
        self.sTime = datetime.now()
        self.nType = MSG_TYPE_CTRL

    def _read_message_length(self, received_byte):
        # self.oMsg.nLen = received_byte
        self.nLen = received_byte

    def _read_message_id(self):
        # next byte: Message ID       
        # self.oMsg.nID = ord(self.reader.read())
        self.nID = ord(self.reader.read())

    def _read_message_counter(self):
        # next byte: Message Counter
        # self.oMsg.nCounter = ord(self.reader.read())
        self.nCounter = ord(self.reader.read())

    def _read_payload(self):
        # Data Length = Message Length without the header and checksum
        # nDataLen = self.oMsg.nLen - 4 - 1
        nDataLen = self.nLen - 4 - 1
        # Extract just the payload data
        # self.oMsg.anData = bytearray(nDataLen)
        self.anData = bytearray(nDataLen)
        for i in range(nDataLen):
            # read Data bytes
            received_byte = ord(self.reader.read())
            # self.oMsg.anData[i] = received_byte
            self.anData[i] = received_byte
            # "2" in data stream is followed by "0" ...
            if received_byte == 2:         
                # this should be a 0 ...        
                self.reader.read()              
        # self.oMsg.nChecksum = ord(self.reader.read())
        self.nChecksum = ord(self.reader.read())

    def _validate_message(self):
        """return CRC check"""
        try:
            signal_map = self.signal_maps[self.nID]
            self.oMsg = KWBMessage(message_id=self.nID, message_type=self.nType, checksum=self.nChecksum, counter=self.nCounter, data=self.anData, length=self.nLen, signal_map=signal_map)
        except IndexError:
            # We lose bytes when a read times out which causes an IndexError
            return False
        return self.oMsg.is_crc_ok()

    def _read_message(self, received_byte):
        self._read_message_length(received_byte) # current byte: Message Length
        self._read_message_id() # next byte: Message ID
        self._read_message_counter() # next byte: Message Counter
        self._read_payload()

    def _found_message(self, received_byte):
        if received_byte == 0:
            # header invalid -> start again
            # 0 is an escape value indicating that this is not a header
            self.state = STATE_WAIT_FOR_HEADER
        elif received_byte == 2:
            # extended header -> SenseMessage
            self.state = STATE_READ_MSG
            # self.oMsg.nType = MSG_TYPE_SENSE
            self.nType = MSG_TYPE_SENSE
        else:
            # valid header -> read in payload
            try:
                self._read_message(received_byte)
            except ValueError:
                # We get "ValueError: negative count" on a bad read
                pass
            finally:
                self.receive_finished = True

    def _read_once(self):
        # read one byte
        received_byte = ord(self.reader.read())

        if self.state == STATE_WAIT_FOR_HEADER and received_byte == 2:
            self._found_header()
        elif self.state == STATE_READ_MSG:
            self._found_message(received_byte)
        else:
            pass # TODO?

    def open(self):
        self.reader.open()

    def close(self):
        self.reader.close()

    def read_forever(self):
        while True:
            try:
                self._read_once()
            except TimeoutError:
                if self._reconnect:
                    self.open()
                    continue
            is_ok = self._validate_message()
            if is_ok:
                yield self.oMsg

    def read_messages(self, message_ids = [], timeout=None):
        """Read message stream until we have one each of the given message ids

        If message_ids are supplied, each message id will only be yielded once.
        When all are yielded, method till return.

        If timeout is supplied, messages will be read until 1) timeout elapses or 
        2) all messages_ids are seen (assuming messages_ids are provided).
        Timeout will happen even if all message_ids have not been seen.
        """

        # If there is no timeout specified, never time out
        timeout_at = datetime.now() + timedelta(0, timeout) if timeout else None

        seen_message_ids = []
        for message in self.read_forever():
            
            # if timeout has elapsed, return False
            if timeout_at and datetime.now() > timeout_at:
                return False
            
            if not message_ids or len(message_ids) == 0:
                # seen message ids are irrelevant, so just yield
                yield message
            elif (message_ids and len(message_ids) > 0) and message.message_id not in seen_message_ids:
                # No message ids, so just yield each message once  until timeout
                seen_message_ids.append(message.message_id)
                yield message
            elif message_ids and message.message_id in message_ids:
                message_ids.remove(message.message_id)
                seen_message_ids.append(message.message_id)
                yield message

            if message_ids and len(message_ids) == 0:
                return

    def read_data(self, message_ids=[], timeout=None):

        boiler_nominal_power_kW = self.heater_config.get('boiler_nominal_power_kW', 1)
        pellet_nominal_energy_kwh_kg = self.heater_config.get('pellet_nominal_energy_kwh_kg', 1)
        # Divide by 100 to make this a multiplication factor
        efficiency = self.heater_config.get('boiler_efficiency', 100) / 100
       
        # boiler_output is decimal percentage of boiler_nominal_power_kW
        boiler_output = 0.0

        data = {}
        for message in self.read_messages(message_ids, timeout):

            # Current number of milliseconds since system started
            timestamp_msec = time.time_ns() / 1000000

            for signal_key, signal_payload in message.decode().items():
                signal_value = signal_payload[0]
                data[signal_key] = signal_value

                # Accumulate some values we need for calculations
                if signal_key == 'boiler_output':
                    # Divide by 100 to make this a multiplication factor
                    boiler_output = signal_value / 100

            # Calculate time deltas
            deltat_sec = (timestamp_msec - self.last_timestamp_msec) / 1000
            deltat_hr = deltat_sec / 60 / 60

            if boiler_output > 0:
                boiler_on = 1
                self.run_time_sec += deltat_sec
                # Calculate aggregates if heater constants are set
                if boiler_nominal_power_kW and pellet_nominal_energy_kwh_kg:
                    # Total energy in kWh that has been produced
                    delta_energy_kWh = deltat_hr * boiler_output * boiler_nominal_power_kW
                    self.energy_kWh += delta_energy_kWh
                    # Pellet consumption_[kg] = Sum(dt_[s] * Real_boiler output_[%] * Boiler_nominal power_[kW]) / (pellet_nominal energy[kwh/kg] * efficiency)
                    self.pellet_consumption_kg += delta_energy_kWh / ( pellet_nominal_energy_kwh_kg * efficiency )
            else:
                boiler_on = 0

            self.last_timestamp_msec = timestamp_msec
            
            data.update({
                'boiler_on': boiler_on,
                'boiler_nominal_power': boiler_nominal_power_kW,
                'boiler_run_time': self.run_time_sec,
                'energy_output': self.energy_kWh,
                'pellet_consumption': self.pellet_consumption_kg,
                'last_timestamp': self.last_timestamp_msec
            } )

            yield data
            

    def read_data_once(self, message_ids, timeout):
        if not message_ids or not timeout or len(message_ids) == 0:
            raise NotImplementedError('read_data_once() requires message ids and a timeout')
        datas = [d for d in self.read_data(message_ids, timeout)]
        return datas[-1]
    

def main():
    """Main method for debug purposes."""

    from pprint import pprint
    import argparse

    parser = argparse.ArgumentParser()
    
    def list_of_ints(arg):
        return list(map(int, arg.split(',')))

    group_read = parser.add_argument_group('Read')
    group_read.add_argument('--once', dest='read', action='store_const', const='once', help="Read certain message ids and exit")
    group_read.add_argument('--ids', dest='message_ids', help="Specify message ids", type=list_of_ints)
    group_read.add_argument('--timeout', dest='timeout', help="Specify timeout for reading message ids", default=2, type=int)
    group_tcp = parser.add_argument_group('TCP')
    group_tcp.add_argument('--tcp', dest='mode', action='store_const', const=PROP_MODE_TCP, help="Set tcp mode")
    group_tcp.add_argument('--host', dest='hostname', help="Specify hostname", default=TCP_IP)
    group_tcp.add_argument('--port', dest='port', help="Specify port", default=TCP_PORT, type=int)
    group_serial = parser.add_argument_group('Serial')
    group_serial.add_argument('--serial', dest='mode', action='store_const', const=PROP_MODE_SERIAL, help="Set serial mode")
    group_serial.add_argument('--interface', dest='interface', help="Specify interface", default=SERIAL_INTERFACE)
    group_serial.add_argument('--baud', dest='baud', help="Specify data rate", default=SERIAL_SPEED)
    group_file = parser.add_argument_group('File')
    group_file.add_argument('--file', dest='mode', action='store_const', const=PROP_MODE_FILE, help="Set file mode")
    group_file.add_argument('--name', dest='file', help="Specify file name", default='')
    group_file.add_argument('--encoding', dest='encoding', help="Specify file encoding", default='utf8')
    group_last = parser.add_argument_group('Last Values')
    group_last.add_argument('--last-energy-output', dest='last_energy_output', help="Previous energy output [kWh]", default=0.0, type=float)
    group_last.add_argument('--last-pellet-consumption', dest='last_pellet_consumption', help="Previous pellet consumption [kg]", default=0.0, type=float)
    group_last.add_argument('--last-run-time', dest='last_run_time', help="Previous boiler run time [sec]", default=0.0, type=float)
    group_last.add_argument('--last-timestamp', dest='last_timestamp', help="Previous timestamp [msec]", default=0, type=int)
    group_heater = parser.add_argument_group('Heater Properties')
    group_heater.add_argument('--boiler-power', dest='boiler_nominal_power_kW', help="Nominal boiler power output [kW]", default=1, type=float)
    group_heater.add_argument('--boiler-efficiency', dest='boiler_efficiency', help="Boiler efficiency [%]", default=1, type=float)
    group_pellets = parser.add_argument_group('Pellet Properties')
    group_pellets.add_argument('--pellet-energy', dest='pellet_nominal_energy_kWh_kg', help="Pellet nominal energy [kWh/kg]", default=1, type=float)
    group_output = parser.add_argument_group('Output')
    group_output.add_argument('--dump', dest='dump', action='store_const', const='dump', help="Dump message as table of flags and values")
    group_serial.add_argument('--aggregation', dest='aggregation', help="Specify data or message level aggregation", default='data')
    args = parser.parse_args()

    # Build ByteReader
    if args.mode == PROP_MODE_TCP:
        reader = TCPByteReader(ip=args.hostname, port=args.port)
    elif args.mode == PROP_MODE_SERIAL:
        reader = SerialByteReader(dev=args.interface, baud=args.baud)
    elif args.mode == PROP_MODE_FILE:
        reader = FileByteReader(path=args.name, encoding=args.encoding)
    else:
        parser.print_help()
        return -1

    # Load up signal maps
    signal_maps = load_signal_maps()

    # Build message generator
    last_values={
        'energy_output': args.last_energy_output,
        'pellet_consumption': args.last_pellet_consumption,
        'boiler_run_time': args.last_run_time,
        'last_timestamp': args.last_timestamp
    }
    heater_config = {
        'pellet_nominal_energy_kWh_kg': args.pellet_nominal_energy_kWh_kg,
        'boiler_efficiency': args.boiler_efficiency,
        'boiler_nominal_power_kW': args.boiler_nominal_power_kW
    }
    message_stream = KWBMessageStream(reader=reader, signal_maps=signal_maps, last_values=last_values, heater_config=heater_config)
    message_stream.open()

    if args.aggregation == 'data':
        if args.read == 'once':
            data = message_stream.read_data_once(message_ids=args.message_ids, timeout=args.timeout)
            pprint(data)
        else:
            message_generator = message_stream.read_data(message_ids=None, timeout=None)
            for data in message_generator:
                pprint(data)
        
    else:  # args.aggregation == 'messages'
        if args.read == 'once':
            message_generator = message_stream.read_messages(args.message_ids, timeout=args.timeout)
        else:
            message_generator = message_stream.read_forever()

        for message in message_generator:
            print('====')
            print('Message Id', message.message_id)
            exclude_none = True
            exclude_zero = True
        
            if (args.dump):
                dump = message.dump()
                # Print flags
                for sensor_name, sensor_dump in dump['flag'].items():
                    if sensor_name.endswith('_00'):
                        print()
                        print(sensor_name, sensor_dump[0], end='')
                    else:
                        print(' ', sensor_dump[0], end='')
                print("\n")
        
                # Print values
                for sensor_type in ['temp', 'ms', 'mbar', 'rpm']:
                    for sensor_name, sensor_dump in dump[sensor_type].items():
                        if exclude_none and sensor_dump[0] is not None:
                            print(sensor_name, sensor_dump[0], sensor_dump[1][3])
                    print("\n")
            else:
                pprint(message.decode())

    message_stream.close()


if __name__ == "__main__":
    main()
