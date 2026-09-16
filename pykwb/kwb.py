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

import asyncio
import struct
import logging
import socket
import time
import threading
import argparse
import serial

if __name__ == "__main__" and not __package__:
    # Direct script execution puts pykwb/, not its parent, on sys.path.
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pykwb.messages import load_messages

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
PROP_PACKET_SENSE_64 = 64

PROP_SENSOR_TEMPERATURE = 0
PROP_SENSOR_FLAG = 1
PROP_SENSOR_RAW = 2
PROP_SENSOR_NUMBER = 3
PROP_SENSOR_PRESSURE = 4
PROP_SENSOR_DURATION = 5
PROP_SENSOR_SPEED = 6

TCP_IP = "127.0.0.1"
TCP_PORT = 23

SERIAL_INTERFACE = "/dev/ttyUSB0"
SERIAL_SPEED = 19200

_LOGGER = logging.getLogger(__name__)


class KWBEasyfireSensor:
    """This Class represents as single sensor."""

    def __init__(self, _packet, _index, _name, _sensor_type, _bit=None,
                 _length=2, _signed=True, _scale=0.1, _units="", _key=""):

        self._packet = _packet
        self._index = _index
        self._bit = _bit
        self._name = _name
        self._sensor_type = _sensor_type
        self._value = None
        self._available = False
        self._length = _length
        self._signed = _signed
        self._scale = _scale
        self._units = _units
        self._key = _key

    @classmethod
    def from_message(cls, message):
        """Create a sensor from one packet definition in messages.csv."""
        if message['type'] == 'bit':
            sensor_type = PROP_SENSOR_FLAG
        elif message['type'] == 'int':
            sensor_type = {
                'C': PROP_SENSOR_TEMPERATURE,
                'mbar': PROP_SENSOR_PRESSURE,
                'ms': PROP_SENSOR_DURATION,
                'msec': PROP_SENSOR_DURATION,
                'sec': PROP_SENSOR_DURATION,
                'rpm': PROP_SENSOR_SPEED,
            }.get(message['units'], PROP_SENSOR_NUMBER)
        else:
            raise ValueError("Unsupported sensor type: " + message['type'])
        return cls(
            int(message['message_id']), int(message['offset']),
            message['name_en'] or message['name_de'] or message['key'],
            sensor_type,
            _bit=int(message['bit']) if message['bit'] else None,
            _length=int(message['length'] or 1),
            _signed=message['signed'] == '1',
            _scale=float(message['scale'] or 1),
            _units=message['units'], _key=message['key'],
        )

    @property
    def key(self):
        """Return the optional CSV key (not necessarily unique)."""
        return self._key

    def decode(self, packet):
        """Update from an unescaped, big-endian payload."""
        if self.sensor_type == PROP_SENSOR_RAW:
            self.value = packet
            return
        offset = self.index
        length = 1 if self.sensor_type == PROP_SENSOR_FLAG else self._length
        if offset is None or offset < 0 or offset + length > len(packet):
            self.value = None
        elif self.sensor_type == PROP_SENSOR_FLAG:
            self.value = ((packet[offset] >> self.bit) & 1
                          if self.bit is not None and 0 <= self.bit < 8 else None)
        else:
            value = int.from_bytes(packet[offset:offset + length], 'big',
                                   signed=self._signed)
            if self.sensor_type == PROP_SENSOR_TEMPERATURE and value == 1300:
                self.value = None
            else:
                self.value = round(value * self._scale, 10)

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
        """Return the sensor's measurement or data type."""
        return self._sensor_type

    @property
    def unit_of_measurement(self):
        """Return the CSV unit, displaying Celsius as °C."""
        if (self._sensor_type == PROP_SENSOR_TEMPERATURE):
            return "°C"
        else:
            return self._units

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
        self._packet_parser = None

        self._mode = _mode
        self._ip = _ip
        self._port = _port
        self._serial_device = _serial_device
        self._serial_speed = _serial_speed
        self._file_path = _file_path
        self._logdatalen = 1024
        self._logdata = []

        self._sensors = {
            PROP_PACKET_SENSE: [
                KWBEasyfireSensor(PROP_PACKET_SENSE, 0, "RAW SENSE", PROP_SENSOR_RAW),
            ],
            PROP_PACKET_CTRL: [
                KWBEasyfireSensor(PROP_PACKET_CTRL, 0, "RAW CTRL", PROP_SENSOR_RAW),
            ],
            PROP_PACKET_SENSE_64: [
                KWBEasyfireSensor(PROP_PACKET_SENSE_64, 0, "RAW SENSE 64", PROP_SENSOR_RAW),
            ],
        }
        for message in load_messages():
            message_id = int(message['message_id'])
            if message_id in self._sensors:
                self._sensors[message_id].append(KWBEasyfireSensor.from_message(message))

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

        self._record_byte(ord(to_return))
        return to_return

    def _record_byte(self, value):
        """Keep identical diagnostics for synchronous and async input."""
        _LOGGER.debug("READ: %s", value)
        self._logdata.append(value)
        if len(self._logdata) > self._logdatalen:
            self._logdata = self._logdata[-self._logdatalen:]
        self._debug(PROP_LOGLEVEL_TRACE, "READ: " + str(value))

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
        while True:
            packet = self._consume_byte(self._read_ord_byte())
            if packet is not None:
                return packet

    def _consume_byte(self, value):
        """Retain partial framing state across reads and listening sessions."""
        if self._packet_parser is None:
            self._packet_parser = self._parse_packet()
            next(self._packet_parser)
        try:
            self._packet_parser.send(value)
        except StopIteration as complete:
            self._packet_parser = None
            return complete.value
        return None

    def _parse_packet(self):
        """Accept bytes via send(), returning one valid, unescaped frame."""
        pending_length = None
        while True:
            if pending_length is None:
                if (yield) != 2:
                    continue
                length = (yield)
            else:
                length = pending_length
                pending_length = None

            if length == 0:
                continue
            mode = PROP_PACKET_CTRL
            while length == 2:
                mode = PROP_PACKET_SENSE
                length = (yield)
            if length < 5:
                continue

            version = (yield)
            counter = (yield)
            checksum = 2
            for value in (length, version, counter):
                checksum = self._add_to_checksum(checksum, value)

            # Length includes the four header bytes and the checksum, but
            # excludes the extra sense header and payload escape padding.
            packet = bytearray()
            valid = True
            for _ in range(length - 5):
                value = (yield)
                packet.append(value)
                checksum = self._add_to_checksum(checksum, value)
                if value == 2:
                    padding = (yield)
                    if padding != 0:
                        # An unescaped 2 starts a new frame. Reuse its next
                        # byte as the length (or extra sense header), rather
                        # than discarding the beginning of that frame.
                        pending_length = padding
                        valid = False
                        break
            if not valid:
                continue
            if (yield) != checksum:
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
        if version not in (PROP_PACKET_SENSE, PROP_PACKET_SENSE_64):
            return
        for sensor in self._sensors[version]:
            sensor.decode(packet)

        for sensor in self._sensors[version]:
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

        for sensor in self._sensors[PROP_PACKET_CTRL]:
            sensor.decode(packet)

        if version == 33:
            self._debug(PROP_LOGLEVEL_INFO, "ID 33 control values:\n" +
                        "\n".join(str(sensor) for sensor in self._sensors[PROP_PACKET_CTRL]))

    def get_sensors(self):
        """Return the list of sensors."""
        return [sensor for sensors in self._sensors.values() for sensor in sensors]

    def __str__(self):
        """Returns an informational text representation of the object."""
        ret = ""

        for sensor in self.get_sensors():
            ret = ret + str(sensor) + "\n"

        return ret

    def _decode_packet(self, mode, version, packet):
        """Decode only configured message IDs with matching frame types."""
        if mode == PROP_PACKET_SENSE and version in (PROP_PACKET_SENSE, PROP_PACKET_SENSE_64):
            self._decode_sense_packet(version, packet)
        elif mode == PROP_PACKET_CTRL and version == PROP_PACKET_CTRL:
            self._decode_ctrl_packet(version, packet)

    def run(self):
        """Read synchronously until stopped or input closes."""
        while self._run_thread:
            try:
                packet = self._read_packet()
            except EOFError:
                self._run_thread = False
                return
            self._decode_packet(*packet)

    def run_thread(self):
        """Start the background listener."""
        self._run_thread = True
        self._thread.start()

    async def _read_async_byte(self):
        if self._mode == PROP_MODE_TCP:
            data = await asyncio.get_running_loop().sock_recv(self._socket, 1)
            if not data:
                raise EOFError("Input connection closed")
        elif self._mode == PROP_MODE_SERIAL:
            # timeout=0 makes serial reads nonblocking on all platforms.
            while True:
                data = self._serial.read(1)
                if data:
                    break
                await asyncio.sleep(0.01)
        elif self._mode == PROP_MODE_FILE:
            return self._read_ord_byte()
        else:
            raise ValueError("Unsupported input mode")
        value = data[0]
        self._record_byte(value)
        return value

    async def listen_forever(self):
        """Update sensors until EOF or task cancellation, without a worker thread.

        Partial packets survive cancellation. Connection construction remains
        synchronous; TCP/serial blocking settings are restored on exit.
        """
        if self._mode == PROP_MODE_TCP:
            timeout = self._socket.gettimeout()
            self._socket.setblocking(False)
        elif self._mode == PROP_MODE_SERIAL:
            timeout = self._serial.timeout
            self._serial.timeout = 0
        try:
            while True:
                # Yield even when input is buffered so deadlines and
                # cancellation work under continuous traffic.
                await asyncio.sleep(0)
                try:
                    value = await self._read_async_byte()
                except EOFError:
                    return
                packet = self._consume_byte(value)
                if packet is not None:
                    self._decode_packet(*packet)
        finally:
            if self._mode == PROP_MODE_TCP:
                self._socket.settimeout(timeout)
            elif self._mode == PROP_MODE_SERIAL:
                self._serial.timeout = timeout

    async def listen_for(self, seconds=1):
        """Update sensors for at most seconds, or until EOF; preserve partial input."""
        if not 0 <= seconds < float('inf'):
            raise ValueError("seconds must be finite and non-negative")
        if seconds == 0:
            return
        try:
            await asyncio.wait_for(self.listen_forever(), timeout=seconds)
        except asyncio.TimeoutError:
            pass

    def stop_thread(self):
        """Stop the main thread."""
        self._run_thread = False

    def is_alive(self):
        """Determine if thread is alive."""
        return self._thread.is_alive()


def _print_summary(kwb):
    """Print sensor values in alphabetical order."""
    print("\n\n---\nSUMMARY: " + time.strftime("%Y-%m-%d %H:%M:%S %Z"))
    for sensor in sorted(kwb.get_sensors(), key=lambda sensor: sensor.name.casefold()):
        if sensor.sensor_type != PROP_SENSOR_RAW:
            print(sensor)


async def _listen_with_summaries(kwb, seconds, summary):
    """Keep listening while reporting periodically, until EOF or cancellation."""
    listener = asyncio.create_task(kwb.listen_forever())
    try:
        while True:
            done, _ = await asyncio.wait({listener}, timeout=seconds)
            if done:
                listener.result()
            if summary:
                _print_summary(kwb)
            if done:
                break
    finally:
        listener.cancel()
        try:
            await listener
        except asyncio.CancelledError:
            pass


def main():
    """Main method for debug purposes."""
    parser = argparse.ArgumentParser()
    group_execution = parser.add_argument_group('Execution')
    group_execution.add_argument('--mode', dest='execution_mode', choices=('thread', 'async'),
                                 default='thread', help="Execution mode (default: thread)")
    group_execution.add_argument('--wait', type=float, default=5,
                                 help="Seconds to listen, or summary interval with --forever (default: 5)")
    group_execution.add_argument('--forever', action='store_true', default=False,
                                 help="Listen continuously, printing summaries every --wait seconds")
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
                                help="Print sensor summaries (default: true)")
    args = parser.parse_args()
    if not 0 <= args.wait < float('inf'):
        parser.error('--wait must be a finite, non-negative number')
    if args.forever and args.wait == 0:
        parser.error('--wait must be positive with --forever')

    kwb = KWBEasyfire(args.mode, args.hostname, args.port, args.interface, 0, args.file)
    if args.log == 'false':
        kwb._debug_level = PROP_LOGLEVEL_NONE
    # Run in either async loop or thread
    try:
        if args.execution_mode == 'async':
            if args.forever:
                asyncio.run(_listen_with_summaries(kwb, args.wait, args.summary == 'true'))
            else:
                asyncio.run(kwb.listen_for(seconds=args.wait))
        else:
            kwb.run_thread()
            try:
                while True:
                    time.sleep(args.wait)
                    if not args.forever:
                        break
                    if args.summary == 'true':
                        _print_summary(kwb)
                    if not kwb.is_alive():
                        break
            finally:
                kwb.stop_thread()
    except KeyboardInterrupt:
        return
    # Print summary
    if not args.forever and args.summary == 'true':
        _print_summary(kwb)


if __name__ == "__main__":
    main()
