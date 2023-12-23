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


Support for KWB Easyfire central heating units.
"""

import logging
import csv
import os
from datetime import datetime, timedelta
from .readers import SerialByteReader, TCPByteReader, FileByteReader


def load_signal_maps(path='config/KWB Protocol - Messages.csv', source=10, message_ids=[32,33,64,65]):
    signal_maps = [{} for i in range(255)]
    filepath = os.path.join(os.path.dirname(__file__), path)
    with open(filepath) as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            row_message_id = int(row['message_id'])
            row_source = int(row['source'])
            if (row_source == source and row_message_id in message_ids):
                if row['type'] == 'bit':
                    sig = ('b', int(row['offset']), int(row['bit']), row['key'], row['sensor_class'] ,row['device_class'])
                elif row['type'] == 'int':
                    sig = ('s' if int(row['signed']) else 'u', int(row['offset']), int(row['length']), float(row['scale']), row['units'], row['key'], row['sensor_class'] ,row['device_class'] )
                else:
                    continue
                signal_maps[row_message_id][row['name_en']] = sig
    return signal_maps


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
                # aSignalValues[strSignalName] = value
                sensor_values[sensor_name] = (value, *aSig)
            else:
                # Name: Type, Offset, Length, Factor, Unit
                value = self.get_value(
                    aSig[1], aSig[2], aSig[3], aSig[0] == 's')
                # aSignalValues[strSignalName] = value
                sensor_values[sensor_name] = (value, *aSig)
        # else:
        #     # If we have no signal map, decode data payload as if it was all temperatures
        #     for nOffset in range(0, self.nLen-6, 2):
        #         strSignalName = ("Offset_%02d (%03d, %03d)" % (
        #             nOffset, self.anData[nOffset], self.anData[nOffset+1]))
        #         aSignalValues[strSignalName] = self.GetValue(nOffset)
        return sensor_values

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

    def __init__(self, reader):
        self._reader = reader

    def open(self):
        self._reader.open()

    def close(self):
        self._reader.close()

    ## CRC computation

    @staticmethod
    def _byte_rot_left(byte, distance):
        """Rotate a byte left by distance bits."""
        return ((byte << distance) | (byte >> (8 - distance))) % 256

    def _add_to_checksum(self, checksum, value):
        """Add a byte to the checksum."""
        checksum = self._byte_rot_left(checksum, 1)
        checksum = checksum + value
        if (checksum > 255):
            checksum = checksum - 255
        # _LOGGER.debug("C: " + str(checksum) + " V: " + str(value))
        return checksum

    ## Message Input

    # pylint: disable=too-many-branches, too-many-statements
    def read_message(self) -> KWBMessage | None:
        """Read a message from the input."""

        # We discover all of these as we loop over the byte stream
        status = STATUS_WAITING
        mode = 0
        checksum = 0
        # checksum_calculated = 0
        length = 0
        message_id = 0
        i = 0
        counter = 0
        packet = bytearray(0)

        # Loop over byte stream until we have a valid packet
        while (status != STATUS_PACKET_DONE):

            # Read in a byte
            read = ord(self._reader.read())

            # If we are not currently reading in the checksum,
            # then add whatever we just read to the checksum calculator
            # if (status != STATUS_CTRL_READ_CHECKSUM and status != STATUS_SENSE_READ_CHECKSUM):
            #     checksum_calculated = self._add_to_checksum(checksum_calculated, read)

            if (status == STATUS_WAITING):
                # A byte == 2 received while in WAITING state indicates the start of a packet
                if (read == 2):
                    status = STATUS_IS_PACKET
                    # checksum_calculated = read
                else:
                    # We're in the middle of a packet, so just keep waiting for another beginning
                    status = STATUS_WAITING
            elif (status == STATUS_IS_PACKET):
                checksum = 0
                if (read == 2):
                    # We found a 2 in byte 2 position, indicating a sense message
                    status = STATUS_IS_SENSE_PACKET
                    # checksum_calculated = read
                    # TODO record that this is a sense message
                elif (read == 0):
                    status = STATUS_WAITING
                else:
                    # We found other than a 2 in byte 2 position, indicating a control message
                    status = STATUS_IS_CTRL_PACKET
                    # TODO record that this is a control message
            elif (status == STATUS_IS_SENSE_PACKET):
                # Read in message length
                length = read
                status = STATUS_SENSE_READ_MESSAGE_ID
            elif (status == STATUS_SENSE_READ_MESSAGE_ID):
                # Read in message id
                message_id = read
                status = STATUS_SENSE_READ_COUNTER
            elif (status == STATUS_SENSE_READ_COUNTER):
                counter = read
                i = 0
                status = STATUS_SENSE_READ_PAYLOAD
            elif (status == STATUS_SENSE_READ_PAYLOAD):
                packet.append(read)
                i = i + 1
                # If we've read in the entire message length, get ready to read in checksum
                if (i == length):
                    status = STATUS_SENSE_READ_CHECKSUM
            elif (status == STATUS_SENSE_READ_CHECKSUM):
                # Read in checksum
                checksum = read
                mode = PROP_PACKET_SENSE
                status = STATUS_PACKET_DONE
            elif (status == STATUS_IS_CTRL_PACKET):
                length = read
                status = STATUS_CTRL_READ_COUNTER
            elif (status == STATUS_CTRL_READ_MESSAGE_ID):
                message_id = read
                status = STATUS_CTRL_READ_COUNTER
            elif (status == STATUS_CTRL_READ_COUNTER):
                counter = read
                i = 0
                status = STATUS_CTRL_READ_PAYLOAD
            elif (status == STATUS_CTRL_READ_PAYLOAD):
                packet.append(read)
                i = i + 1
                if (i == length):
                    status = STATUS_CTRL_READ_CHECKSUM
            elif (status == STATUS_CTRL_READ_CHECKSUM):
                checksum = read
                mode = PROP_PACKET_CTRL
                status = STATUS_PACKET_DONE
            else:
                status = STATUS_WAITING

        _LOGGER.debug("MODE: " + str(mode) + " Message Id: " + str(message_id) + " Checksum: " + str(checksum) + " Count: " + str(counter) + " Length: " + str(len(packet)))
        _LOGGER.debug("Packet: " + str(packet))
        
        signal_map = SIGNAL_MAPS[message_id]
        message = KWBMessage(message_id=message_id, length=length, counter=counter, data=packet, checksum=checksum, message_type=mode, signal_map=signal_map)
        if not message.is_crc_ok():
            _LOGGER.debug('Read message with bad CRC %s. Throwing message away.' % message.get_crc())
            return None
        return message

    def read_forever(self):
        while True:
            # Read a message
            message = self.read_message()
            if message:
                yield message


STATE_WAIT_FOR_HEADER = 1
STATE_READ_MSG = 2
MSG_TYPE_CTRL = 1
MSG_TYPE_SENSE = 2
class KWBMessageStreamLogkwb():

    def __init__(self, reader: TCPByteReader, signal_maps):
        self.reader = reader
        self.state = STATE_WAIT_FOR_HEADER
        self.receive_finished = False
        # self.oMsg: KWBMessage = KWBMessage()
        self.signal_maps = signal_maps

        # State vars
        self.sTime = 0
        self.nType = 0
        self.nLen = 0
        self.nID = 0
        self.nCounter = 0
        self.anData = bytearray(0)
        self.nChecksum = 0
        self.oMsg = None

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
        # return CRC check
        # return self.oMsg.IsCrcOk() # boolean
        signal_map = self.signal_maps[self.nID]
        self.oMsg = KWBMessage(message_id=self.nID, message_type=self.nType, checksum=self.nChecksum, counter=self.nCounter, data=self.anData, length=self.nLen, signal_map=signal_map)
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
            self._read_once()
            is_ok = self._validate_message()
            if is_ok:
                yield self.oMsg

    def read_messages(self, message_ids = [], timeout=5):
        """Read message stream until we have one each of the given message ids"""

        timeout_at = datetime.now() + timedelta(0, timeout)

        seen_message_ids = []
        for message in self.read_forever():
            
            # if timeout has elapsed, return False
            if datetime.now() > timeout_at:
                return False
            
            if (not message_ids or not len(message_ids)) and message.message_id not in seen_message_ids:
                # No message ids, so just yield each message once  until timeout
                seen_message_ids.append(message.message_id)
                yield message
            elif message_ids and message.message_id in message_ids:
                message_ids.remove(message.message_id)
                seen_message_ids.append(message.message_id)
                yield message

            if message_ids and len(message_ids) == 0:
                return


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
    message_stream = KWBMessageStreamLogkwb(reader, signal_maps)
    message_stream.open()

    if args.read == 'once':
        message_generator = message_stream.read_messages(args.message_ids, timeout=3)
    else:
        message_generator = message_stream.read_forever()
    for message in message_generator:
        print('====')
        print('Message Id', message.message_id)
        pprint(message.decode())
    
    message_stream.close()


if __name__ == "__main__":
    main()
