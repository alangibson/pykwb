"""CSV sensor construction and decoding beyond the original sensor lists."""
import unittest

from pykwb.kwb import KWBEasyfire, PROP_SENSOR_RAW


class MessageSensorTests(unittest.TestCase):
    def setUp(self):
        self.reader = KWBEasyfire(-1)
        self.reader._debug_level = 0

    def sensor(self, name):
        return next(s for s in self.reader.get_sensors() if s.name == name)

    def test_csv_definitions_and_raw_diagnostics(self):
        sensors = self.reader.get_sensors()
        self.assertEqual(sum(s.sensor_type != PROP_SENSOR_RAW for s in sensors), 57)
        self.assertEqual(sum(s.sensor_type == PROP_SENSOR_RAW for s in sensors), 2)
        self.assertEqual(self.sensor('Heater Temp').key, 'heater_temp')
        self.assertEqual(self.sensor('Heater Temp').unit_of_measurement, '°C')
        self.assertEqual(self.sensor('Pressure').unit_of_measurement, 'mbar')

    def test_sense_flags_signed_integers_and_scaled_numbers(self):
        payload = bytearray(73)
        payload[3] = 1 << 6
        payload[32:34] = (-123).to_bytes(2, 'big', signed=True)
        payload[34:36] = (1234).to_bytes(2, 'big')
        payload[69:71] = (100).to_bytes(2, 'big')
        payload[71:73] = (65535).to_bytes(2, 'big')
        self.reader._decode_sense_packet(32, payload)
        self.assertEqual(self.sensor('Ash Can OK').value, 1)
        self.assertEqual(self.sensor('Heater Running').value, 0)
        self.assertEqual(self.sensor('Photodiode').value, -123)
        self.assertAlmostEqual(self.sensor('Pressure').value, 1.234)
        self.assertEqual(self.sensor('Suction Speed').value, 60)
        self.assertEqual(self.sensor('Fan Speed').value, 39321)
        self.reader._decode_sense_packet(32, bytes(34))
        self.assertIsNone(self.sensor('Pressure').value)
        self.assertFalse(self.sensor('Fan Speed').available)

    def test_control_numbers_and_csv_ash_discharge_position(self):
        payload = bytearray(17)
        payload[2] = 1 << 6
        payload[8] = 255
        payload[10:12] = (123).to_bytes(2, 'big')
        payload[12:14] = (50).to_bytes(2, 'big')
        self.reader._decode_ctrl_packet(33, payload)
        self.assertEqual(self.sensor('Ash Discharge').value, 1)
        self.assertAlmostEqual(self.sensor('Buffer 0 Pumping').value, 100)
        self.assertEqual(self.sensor('Main Drive Cycle Time').value, 1230)
        self.assertEqual(self.sensor('Main Drive Time').value, 500)
        self.assertEqual(self.sensor('Heater Output').value, 50)
        self.reader._decode_ctrl_packet(33, bytes(11))
        self.assertIsNone(self.sensor('Main Drive Cycle Time').value)
        self.assertFalse(self.sensor('Main Drive Time').available)
