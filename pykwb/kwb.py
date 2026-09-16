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

import struct
import logging
import socket
import time
import threading
import argparse
import serial


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
STATUS_PRE_1 = 1
STATUS_SENSE_PRE_2 = 2
STATUS_SENSE_PRE_3 = 3
STATUS_SENSE_PRE_LENGTH = 6
STATUS_SENSE_DATA = 8
STATUS_SENSE_CHECKSUM = 9
STATUS_CTRL_PRE_2 = 10
STATUS_CTRL_PRE_3 = 11
STATUS_CTRL_DATA = 12
STATUS_CTRL_CHECKSUM = 19
STATUS_PACKET_DONE = 255

PROP_PACKET_SENSE = 32
PROP_PACKET_CTRL = 33

PROP_SENSOR_TEMPERATURE = 0
PROP_SENSOR_FLAG = 1
PROP_SENSOR_RAW = 2

TCP_IP = "127.0.0.1"
TCP_PORT = 23

SERIAL_INTERFACE = "/dev/ttyUSB0"
SERIAL_SPEED = 19200

_LOGGER = logging.getLogger(__name__)


class KWBEasyfireSensor:
    """This Class represents as single sensor."""

    def __init__(self, _packet, _index, _name, _sensor_type, _bit=None):

        self._packet = _packet
        self._index = _index
        self._bit = _bit
        self._name = _name
        self._sensor_type = _sensor_type
        self._value = None
        self._available = False

    @property
    def index(self):
        """Return the unescaped payload byte offset, or None if unmapped."""
        return self._index

    @property
    def bit(self):
        """Return the bit position within the payload byte for flags."""
        return self._bit

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
        self._available = _value is not None
        self._value = _value

    @property
    def available(self):
        """Return if sensor is available."""
        return self._available

    def __str__(self):
        """Returns an informational text representation of the sensor."""
        return self.name + ": I: " + str(self.index) + " T: " + str(self.sensor_type) + "(" + str(self.unit_of_measurement) + ") V: " + str(self.value)


# pylint: disable=too-many-instance-attributes
class KWBEasyfire:
    """Communicats with the KWB Easyfire unit."""

    def __init__(self, _mode, _ip="", _port=0, _serial_device="", _serial_speed=19200, _file_path=""):
        """Initialize the Object."""

        self._debug_level = PROP_LOGLEVEL_INFO
        self._run_thread = True

        self._mode = _mode
        self._ip = _ip
        self._port = _port
        self._serial_device = _serial_device
        self._serial_speed = _serial_speed
        self._file_path = _file_path
        self._logdatalen = 1024
        self._logdata = []

        self._sense_sensor = []

        self._sense_sensor.append(KWBEasyfireSensor(PROP_PACKET_SENSE, 0, "RAW SENSE", PROP_SENSOR_RAW))
        self._sense_sensor.append(KWBEasyfireSensor(PROP_PACKET_SENSE, 6, "Heating Circuit 1 Supply", PROP_SENSOR_TEMPERATURE))
        self._sense_sensor.append(KWBEasyfireSensor(PROP_PACKET_SENSE, 8, "Return", PROP_SENSOR_TEMPERATURE))
        self._sense_sensor.append(KWBEasyfireSensor(PROP_PACKET_SENSE, 10, "Boiler 0", PROP_SENSOR_TEMPERATURE))
        self._sense_sensor.append(KWBEasyfireSensor(PROP_PACKET_SENSE, 12, "Furnace", PROP_SENSOR_TEMPERATURE))
        self._sense_sensor.append(KWBEasyfireSensor(PROP_PACKET_SENSE, 14, "Buffer Tank 2", PROP_SENSOR_TEMPERATURE))
        self._sense_sensor.append(KWBEasyfireSensor(PROP_PACKET_SENSE, 16, "Buffer Tank 1", PROP_SENSOR_TEMPERATURE))
        self._sense_sensor.append(KWBEasyfireSensor(PROP_PACKET_SENSE, 18, "Outside", PROP_SENSOR_TEMPERATURE))
        self._sense_sensor.append(KWBEasyfireSensor(PROP_PACKET_SENSE, 20, "Exhaust", PROP_SENSOR_TEMPERATURE))
        self._sense_sensor.append(KWBEasyfireSensor(PROP_PACKET_SENSE, 22, "Furnace Control", PROP_SENSOR_TEMPERATURE))
        self._sense_sensor.append(KWBEasyfireSensor(PROP_PACKET_SENSE, 24, "Heating Circuit 1 Remote", PROP_SENSOR_TEMPERATURE))
        self._sense_sensor.append(KWBEasyfireSensor(PROP_PACKET_SENSE, 26, "Heating Circuit 2 Remote", PROP_SENSOR_TEMPERATURE))
        self._sense_sensor.append(KWBEasyfireSensor(PROP_PACKET_SENSE, 28, "Heating Circuit 2 Supply", PROP_SENSOR_TEMPERATURE))
        self._sense_sensor.append(KWBEasyfireSensor(PROP_PACKET_SENSE, 30, "Stoker Channel", PROP_SENSOR_TEMPERATURE))

        self._ctrl_sensor = []

        self._ctrl_sensor.append(KWBEasyfireSensor(PROP_PACKET_CTRL, 0, "RAW CTRL", PROP_SENSOR_RAW))
        # self._ctrl_sensor.append(KWBEasyfireSensor(PROP_PACKET_CTRL, 0, "Fire Damper", PROP_SENSOR_FLAG, _bit=1))
        # self._ctrl_sensor.append(KWBEasyfireSensor(PROP_PACKET_CTRL, 0, "Alarm 2", PROP_SENSOR_FLAG, _bit=2))
        # self._ctrl_sensor.append(KWBEasyfireSensor(PROP_PACKET_CTRL, 0, "Alarm 1", PROP_SENSOR_FLAG, _bit=3))
        self._ctrl_sensor.append(KWBEasyfireSensor(PROP_PACKET_CTRL, 1, "Power", PROP_SENSOR_FLAG, _bit=2))
        self._ctrl_sensor.append(KWBEasyfireSensor(PROP_PACKET_CTRL, 1, "Heating Circuit 1 Pump", PROP_SENSOR_FLAG, _bit=5))
        self._ctrl_sensor.append(KWBEasyfireSensor(PROP_PACKET_CTRL, 1, "Heating Circuit 2 Pump", PROP_SENSOR_FLAG, _bit=6))
        self._ctrl_sensor.append(KWBEasyfireSensor(PROP_PACKET_CTRL, 1, "Heating Circuit 1 Mixer On", PROP_SENSOR_FLAG, _bit=7))
        self._ctrl_sensor.append(KWBEasyfireSensor(PROP_PACKET_CTRL, 2, "Heating Circuit 1 Mixer Closed", PROP_SENSOR_FLAG, _bit=0))
        self._ctrl_sensor.append(KWBEasyfireSensor(PROP_PACKET_CTRL, 2, "Heating Circuit 2 Mixer On", PROP_SENSOR_FLAG, _bit=1))
        self._ctrl_sensor.append(KWBEasyfireSensor(PROP_PACKET_CTRL, 2, "Heating Circuit 2 Mixer Closed", PROP_SENSOR_FLAG, _bit=2))
        self._ctrl_sensor.append(KWBEasyfireSensor(PROP_PACKET_CTRL, 2, "Return Mixer On", PROP_SENSOR_FLAG, _bit=3))
        self._ctrl_sensor.append(KWBEasyfireSensor(PROP_PACKET_CTRL, 2, "Return Mixer Closed", PROP_SENSOR_FLAG, _bit=4))
        self._ctrl_sensor.append(KWBEasyfireSensor(PROP_PACKET_CTRL, 2, "Boiler 0 Pump", PROP_SENSOR_FLAG, _bit=5))
        self._ctrl_sensor.append(KWBEasyfireSensor(PROP_PACKET_CTRL, 3, "Ash Discharge", PROP_SENSOR_FLAG, _bit=6))
        self._ctrl_sensor.append(KWBEasyfireSensor(PROP_PACKET_CTRL, 3, "Cleaning", PROP_SENSOR_FLAG, _bit=7))
        self._ctrl_sensor.append(KWBEasyfireSensor(PROP_PACKET_CTRL, 9, "Main Relais", PROP_SENSOR_FLAG, _bit=1))
        self._ctrl_sensor.append(KWBEasyfireSensor(PROP_PACKET_CTRL, 9, "Room Discharge", PROP_SENSOR_FLAG, _bit=2))
        self._ctrl_sensor.append(KWBEasyfireSensor(PROP_PACKET_CTRL, 16, "Ignition", PROP_SENSOR_FLAG, _bit=2))

        self._thread = threading.Thread(target=self.run, daemon=True)

        self._open_connection()

    def _debug(self, level, text):
        """Output a debug log text."""
        if (level <= self._debug_level):
            print(text)

    def __del__(self):
        """Destruct the object."""
        self._debug(PROP_LOGLEVEL_DEBUG, self._logdata)
        self._close_connection()

    def _open_connection(self):
        """Open a connection to the easyfire unit."""
        if (self._mode == PROP_MODE_SERIAL):
            self._serial = serial.Serial(self._serial_device, self._serial_speed)
        elif (self._mode == PROP_MODE_TCP):
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.connect((self._ip, self._port))
        elif (self._mode == PROP_MODE_FILE):
            self._file = open(self._file_path, "r")

    def _close_connection(self):
        """Close the connection to the easyfire unit."""
        if (self._mode == PROP_MODE_SERIAL):
            self._serial.close()
        elif (self._mode == PROP_MODE_TCP):
            self._socket.close()
        elif (self._mode == PROP_MODE_FILE):
            self._file.close()

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
        self._debug(PROP_LOGLEVEL_TRACE, "C: " + str(checksum) + " V: " + str(value))
        return checksum

    def _read_byte(self):
        """Read a byte from input."""

        to_return = ""
        if (self._mode == PROP_MODE_SERIAL):
            to_return = self._serial.read(1)
        elif (self._mode == PROP_MODE_TCP):
            to_return = self._socket.recv(1)
        elif (self._mode == PROP_MODE_FILE):
            read = self._file.readline()
            if (read == ''):
                raise EOFError("EOF")
            to_return = struct.pack("B", int(read))

        if not to_return:
            raise EOFError("Input connection closed")

        _LOGGER.debug("READ: " + str(ord(to_return)))
        self._logdata.append(ord(to_return))
        if (len(self._logdata) > self._logdatalen):
            self._logdata = self._logdata[len(self._logdata) - self._logdatalen:]

        self._debug(PROP_LOGLEVEL_TRACE, "READ: " + str(ord(to_return)))

        return to_return

    def _read_ord_byte(self):
        """Read a byte as number from the input."""
        return ord(self._read_byte())

    @staticmethod
    def _sense_packet_to_data(packet):
        """Remove the escape pad bytes from a sense packet (\2\0 -> \2)."""
        data = bytearray(0)
        last = 0
        i = 0
        while (i < len(packet)):
            if not (last == 2 and packet[i] == 0):
                data.append(packet[i])
            last = packet[i]
            i += 1

        return data

    @staticmethod
    def _decode_temp(byte_1, byte_2):
        """Decode a signed short temperature as two bytes to a single number."""
        temp = (byte_1 << 8) + byte_2
        if temp == 1300:
            return None
        if (temp > 32767):
            temp = temp - 65536
        temp = temp / 10
        return temp

    def _read_packet(self):
        """Read a checksum-valid frame and return its unescaped payload."""
        pending_length = None
        while True:
            if pending_length is None:
                if self._read_ord_byte() != 2:
                    continue
                length = self._read_ord_byte()
            else:
                length = pending_length
                pending_length = None

            if length == 0:
                continue
            mode = PROP_PACKET_CTRL
            while length == 2:
                mode = PROP_PACKET_SENSE
                length = self._read_ord_byte()
            if length < 5:
                continue

            version = self._read_ord_byte()
            counter = self._read_ord_byte()
            checksum = 2
            for value in (length, version, counter):
                checksum = self._add_to_checksum(checksum, value)

            # Length includes the four header bytes and the checksum, but
            # excludes the extra sense header and payload escape padding.
            packet = bytearray()
            valid = True
            for _ in range(length - 5):
                value = self._read_ord_byte()
                packet.append(value)
                checksum = self._add_to_checksum(checksum, value)
                if value == 2:
                    padding = self._read_ord_byte()
                    if padding != 0:
                        # An unescaped 2 starts a new frame. Reuse its next
                        # byte as the length (or extra sense header), rather
                        # than discarding the beginning of that frame.
                        pending_length = padding
                        valid = False
                        break
            if not valid:
                continue
            if self._read_ord_byte() != checksum:
                continue

            packet_type = "SENSE" if mode == PROP_PACKET_SENSE else "CTRL"
            summary = "\n\nPacket ID %d %s counter=%d length=%d" % (
                version, packet_type, counter, len(packet))
            if self._debug_level >= PROP_LOGLEVEL_DEBUG:
                summary += " payload=" + packet.hex(" ")
            self._debug(PROP_LOGLEVEL_INFO, summary)
            return (mode, version, packet)

    def _decode_sense_packet(self, version, packet):
        """Decode boiler temperatures using the message ID's payload layout."""
        if version != PROP_PACKET_SENSE:
            return
        for sensor in self._sense_sensor:
            if sensor.sensor_type == PROP_SENSOR_RAW:
                sensor.value = packet
            elif sensor.sensor_type == PROP_SENSOR_TEMPERATURE:
                offset = sensor.index
                if offset is None or offset + 1 >= len(packet):
                    sensor.value = None
                else:
                    sensor.value = self._decode_temp(packet[offset], packet[offset + 1])

        for sensor in self._sense_sensor:
            level = (PROP_LOGLEVEL_DEBUG if sensor.sensor_type == PROP_SENSOR_RAW
                     else PROP_LOGLEVEL_INFO)
            self._debug(level, str(sensor))

    def _decode_ctrl_packet(self, version, packet):
        """Decode a control packet into the list of sensors."""
        if version != PROP_PACKET_CTRL:
            return

        for i in range(min(5, len(packet))):
            input_bit = packet[i]
            self._debug(PROP_LOGLEVEL_DEBUG, "Byte " + str(i) + ": " + str((input_bit >> 7) & 1) + str((input_bit >> 6) & 1) + str((input_bit >> 5) & 1) + str((input_bit >> 4) & 1) + str((input_bit >> 3) & 1) + str((input_bit >> 2) & 1) + str((input_bit >> 1) & 1) + str(input_bit & 1))

        for sensor in self._ctrl_sensor:
            if (sensor.sensor_type == PROP_SENSOR_FLAG):
                offset = sensor.index
                if offset is None or sensor.bit is None or offset >= len(packet):
                    sensor.value = None
                else:
                    sensor.value = (packet[offset] >> sensor.bit) & 1
            elif (sensor.sensor_type == PROP_SENSOR_RAW):
                sensor.value = packet

        if version == 33:
            self._debug(PROP_LOGLEVEL_INFO, "ID 33 control values:\n" +
                        "\n".join(str(sensor) for sensor in self._ctrl_sensor))

    def get_sensors(self):
        """Return the list of sensors."""
        return self._sense_sensor + self._ctrl_sensor

    def __str__(self):
        """Returns an informational text representation of the object."""
        ret = ""

        for sensor in self._sense_sensor:
            ret = ret + str(sensor) + "\n"

        for sensor in self._ctrl_sensor:
            ret = ret + str(sensor) + "\n"

        return ret

    def run(self):
        """Main thread that reads from input and populates the sensors."""
        while (self._run_thread):
            try:
                (mode, version, packet) = self._read_packet()
            except EOFError:
                self._run_thread = False
                return
            if mode == PROP_PACKET_SENSE and version == PROP_PACKET_SENSE:
                self._decode_sense_packet(version, packet)
            elif mode == PROP_PACKET_CTRL and version == PROP_PACKET_CTRL:
                self._decode_ctrl_packet(version, packet)

    def run_thread(self):
        """Run the main thread."""
        self._run_thread = True
        self._thread.start()

    def stop_thread(self):
        """Stop the main thread."""
        self._run_thread = False

    def is_alive(self):
        """Determine if thread is alive."""
        return self._thread.is_alive()


def main():
    """Main method for debug purposes."""
    parser = argparse.ArgumentParser()
    group_tcp = parser.add_argument_group('TCP')
    group_tcp.add_argument('--tcp', dest='mode', action='store_const', const=PROP_MODE_TCP, help="Set tcp mode")
    group_tcp.add_argument('--host', dest='hostname', help="Specify hostname", default='')
    group_tcp.add_argument('--port', dest='port', help="Specify port", default=23, type=int)
    group_serial = parser.add_argument_group('Serial')
    group_serial.add_argument('--serial', dest='mode', action='store_const', const=PROP_MODE_SERIAL, help="Set serial mode")
    group_serial.add_argument('--interface', dest='interface', help="Specify interface", default='')
    group_file = parser.add_argument_group('File')
    group_file.add_argument('--file', dest='mode', action='store_const', const=PROP_MODE_FILE, help="Set file mode")
    group_file.add_argument('--name', dest='file', help="Specify file name", default='')
    group_terminal = parser.add_argument_group('Terminal')
    group_terminal.add_argument('--log', choices=('true', 'false'), default='true',
                                help="Print individual messages (default: true)")
    group_terminal.add_argument('--summary', choices=('true', 'false'), default='true',
                                help="Print final sensor summary (default: true)")
    group_execution = parser.add_argument_group('Execution')
    group_execution.add_argument('--wait', type=float, default=5,
                                 help="Seconds to listen before stopping (default: 5)")
    args = parser.parse_args()
    if not 0 <= args.wait < float('inf'):
        parser.error('--wait must be a finite, non-negative number')

    kwb = KWBEasyfire(args.mode, args.hostname, args.port, args.interface, 0, args.file)
    if args.log == 'false':
        kwb._debug_level = PROP_LOGLEVEL_NONE
    kwb.run_thread()
    time.sleep(args.wait)
    kwb.stop_thread()
    if args.summary == 'true':
        print("\n\n---\nSUMMARY:")
        for sensor in kwb.get_sensors():
            if sensor.sensor_type == PROP_SENSOR_RAW:
                continue
            print(sensor)


if __name__ == "__main__":
    main()
