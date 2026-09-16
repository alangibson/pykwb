"""Regression coverage for boiler temperature layouts and wire framing."""
import unittest
from pathlib import Path
from unittest.mock import patch

from pykwb.kwb import KWBEasyfire, PROP_MODE_FILE, PROP_MODE_TCP, PROP_PACKET_SENSE


ROOT = Path(__file__).resolve().parents[1]


def frame(message_id, payload, sense=True):
    """Encode a frame with the KWB rotating checksum and payload escaping."""
    header = bytes((2, len(payload) + 5, message_id, 1))
    checksum = 0
    for value in header + payload:
        checksum = ((checksum << 1) | (checksum >> 7)) & 255
        checksum += value
        if checksum > 255:
            checksum -= 255
    return ((b'\x02' if sense else b'') + header
            + payload.replace(b'\x02', b'\x02\x00') + bytes((checksum,)))


class TemperatureTests(unittest.TestCase):
    def make_reader(self):
        reader = KWBEasyfire(-1)
        reader._debug_level = 0
        return reader

    def test_signed_temperatures_and_disconnected_sensor(self):
        for encoded, expected in ((b'\x02\x5f', 60.7), (b'\xff\xc9', -5.5),
                                  (b'\x80\x00', -3276.8), (b'\x00\x00', 0),
                                  (b'\x01\xf4', 50), (b'\x05\x14', None)):
            with self.subTest(encoded=encoded):
                self.assertEqual(KWBEasyfire._decode_temp(*encoded), expected)

    def test_framing_escapes_lengths_and_checksum(self):
        reader = self.make_reader()
        # Include an escaped 2 followed by a real zero, plus another escaped 2.
        payload = b'\x02\x00\x02\x07'
        good = frame(32, payload)
        corrupt = good[:-1] + bytes((good[-1] ^ 1,))
        stream = iter(corrupt + good + frame(33, b'\x01' * 24, sense=False))
        with patch.object(reader, '_read_ord_byte', side_effect=lambda: next(stream)):
            self.assertEqual(reader._read_packet(), (PROP_PACKET_SENSE, 32, payload))
            mode, message_id, decoded = reader._read_packet()
            self.assertEqual((mode, message_id, decoded), (1, 33, b'\x01' * 24))

    def test_recorded_boiler_layouts(self):
        cases = (
            ('kwb_17_16.txt', 16, 59,
             [60.7, 53.1, 64.5, 59.0, 58.5, 63.5, 0.4, 64.5,
              None, None, None, None, 34.1]),
            ('kwb_33_32.txt', 32, 62,
             [30.4, 77.5, 45.3, 74.1, None, None, 14.6, 73.1,
              32.4, None, None, None, None]),
        )
        for filename, sense_id, count, expected in cases:
            with self.subTest(filename=filename):
                reader = KWBEasyfire(PROP_MODE_FILE, _file_path=ROOT / 'testdata' / filename)
                reader._debug_level = 0
                self.addCleanup(reader._close_connection)
                counts = {}
                while True:
                    try:
                        mode, message_id, payload = reader._read_packet()
                    except EOFError:
                        break
                    counts[message_id] = counts.get(message_id, 0) + 1
                    if mode == PROP_PACKET_SENSE and counts[message_id] == 1:
                        reader._decode_sense_packet(message_id, payload)
                        sensors = reader._sense_sensor[1:]
                        self.assertEqual([s.value for s in sensors], expected)
                        self.assertEqual([s.available for s in sensors],
                                         [v is not None for v in expected])
                self.assertEqual(counts, {sense_id: count, sense_id + 1: count})

    def test_truncated_payload_recovers_at_next_header(self):
        for sense in (False, True):
            with self.subTest(sense=sense):
                reader = self.make_reader()
                # A frame declaring 20 payload bytes stops after just one.
                truncated = bytes((2, 25, 17, 1, 255))
                payload = b'\x02\x00\x02\x07'
                stream = iter(truncated + frame(32, payload, sense=sense))
                with patch.object(reader, '_read_ord_byte', side_effect=lambda: next(stream)):
                    self.assertEqual(reader._read_packet(), (0 if sense else 1, 32, payload))

    def test_empty_and_short_payloads_do_not_crash_temperature_decoder(self):
        reader = self.make_reader()
        for message_id in (16, 32, 64, 255):
            for length in range(33):
                with self.subTest(message_id=message_id, length=length):
                    reader._decode_sense_packet(message_id, bytes(length))

    def test_closed_tcp_connection_stops_reader_cleanly(self):
        with patch('pykwb.kwb.socket.socket') as socket_factory:
            socket_factory.return_value.recv.return_value = b''
            reader = KWBEasyfire(PROP_MODE_TCP)
            reader._debug_level = 0
            reader.run()
            self.assertFalse(reader._run_thread)

    def test_eof_in_partial_packet_stops_reader_cleanly(self):
        reader = self.make_reader()
        with patch.object(reader, '_read_ord_byte', side_effect=[2, 25, 17, 1, EOFError()]):
            reader.run()
        self.assertFalse(reader._run_thread)

    def test_captured_short_control_frame_keeps_reader_running(self):
        reader = self.make_reader()
        reader._decode_ctrl_packet(17, bytes((255, 255, 255)))
        flags_before = [sensor.value for sensor in reader._ctrl_sensor[1:]]
        payload = bytearray(32)
        payload[12:14] = b'\x02\xe5'
        wire = bytes((2, 7, 0, 65, 27, 82, 62)) + frame(32, payload)
        position = 0

        def read_byte():
            nonlocal position
            value = wire[position]
            position += 1
            if position == len(wire):
                reader._run_thread = False
            return value

        with patch.object(reader, '_read_ord_byte', side_effect=read_byte):
            reader.run()
        self.assertEqual(reader._ctrl_sensor[0].value, bytes((27, 82)))
        self.assertEqual([sensor.value for sensor in reader._ctrl_sensor[1:]], flags_before)
        self.assertEqual(reader._sense_sensor[4].value, 74.1)

    def test_short_known_control_payloads_mark_missing_flags_unavailable(self):
        reader = self.make_reader()
        for message_id in (17, 33):
            for length in range(6):
                with self.subTest(message_id=message_id, length=length):
                    reader._decode_ctrl_packet(message_id, bytes((255,)) * 5)
                    reader._decode_ctrl_packet(message_id, bytes(length))
                    for sensor in reader._ctrl_sensor[1:]:
                        present = sensor.index // 8 < length
                        self.assertEqual(sensor.value, 0 if present else None)
                        self.assertEqual(sensor.available, present)

    def test_unrelated_messages_do_not_overwrite_boiler_temperatures(self):
        reader = self.make_reader()
        payload = bytearray(32)
        payload[12:14] = b'\x02\xe5'
        reader._decode_sense_packet(32, payload)
        reader._decode_sense_packet(64, bytes(24))
        self.assertEqual(reader._sense_sensor[4].value, 74.1)

    def test_disconnected_sensor_clears_previous_reading(self):
        reader = self.make_reader()
        payload = bytearray(32)
        payload[12:14] = b'\x02\xe5'
        reader._decode_sense_packet(32, payload)
        sensor = reader._sense_sensor[4]
        self.assertTrue(sensor.available)
        payload[12:14] = b'\x05\x14'
        reader._decode_sense_packet(32, payload)
        self.assertIsNone(sensor.value)
        self.assertFalse(sensor.available)


if __name__ == '__main__':
    unittest.main()
