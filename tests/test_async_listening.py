"""Async listening uses the same framing and sensors as the synchronous reader."""
import asyncio
from collections import deque
from pathlib import Path
import socket
import unittest
from unittest.mock import patch

from pykwb.kwb import KWBEasyfire, PROP_MODE_FILE, PROP_MODE_TCP, PROP_MODE_SERIAL, PROP_PACKET_CTRL
from test_temperatures import frame


ROOT = Path(__file__).resolve().parents[1]


class AsyncListeningTests(unittest.IsolatedAsyncioTestCase):
    def tcp_reader(self):
        reader = KWBEasyfire(-1)
        reader._debug_level = 0
        receiver, sender = socket.socketpair()
        reader._mode = PROP_MODE_TCP
        reader._socket = receiver
        self.addCleanup(receiver.close)
        self.addCleanup(sender.close)
        return reader, sender

    def furnace(self, reader):
        return next(s.value for s in reader.get_sensors() if s.key == 'heater_temp')

    def temperature_frame(self):
        payload = bytearray(32)
        payload[12:14] = b'\x02\xe5'
        return frame(32, payload)

    async def test_file_replay_matches_synchronous_decoding_without_threads(self):
        path = ROOT / 'testdata' / 'kwb_33_32.txt'
        synchronous = KWBEasyfire(PROP_MODE_FILE, _file_path=path)
        asynchronous = KWBEasyfire(PROP_MODE_FILE, _file_path=path)
        for reader in (synchronous, asynchronous):
            reader._debug_level = 0
            self.addCleanup(reader._close_connection)
        synchronous.run()
        with patch('threading.Thread.start') as start:
            await asynchronous.listen_forever()
        start.assert_not_called()
        self.assertEqual([(s.name, s.value, s.available) for s in synchronous.get_sensors()],
                         [(s.name, s.value, s.available) for s in asynchronous.get_sensors()])

    async def test_idle_tcp_deadline_keeps_event_loop_responsive(self):
        reader, _ = self.tcp_reader()
        ticks = []

        async def heartbeat():
            await asyncio.sleep(0.005)
            ticks.append(True)

        before = asyncio.get_running_loop().time()
        await asyncio.gather(reader.listen_for(seconds=0.03), heartbeat())
        elapsed = asyncio.get_running_loop().time() - before
        self.assertTrue(ticks)
        self.assertGreaterEqual(elapsed, 0.02)
        self.assertLess(elapsed, 1)
        self.assertIsNone(reader._socket.gettimeout())
        self.assertIsNone(self.furnace(reader))
        self.assertFalse(reader.is_alive())

    async def test_partial_escape_survives_listen_for_deadline(self):
        reader, sender = self.tcp_reader()
        wire = self.temperature_frame()
        split = wire.index(b'\x02\x00') + 1
        sender.sendall(wire[:split])
        await reader.listen_for(0.02)
        self.assertIsNone(self.furnace(reader))
        sender.sendall(wire[split:])
        sender.shutdown(socket.SHUT_WR)
        await reader.listen_forever()
        self.assertEqual(self.furnace(reader), 74.1)

    async def test_cancelled_listener_can_resume_partial_packet(self):
        reader, sender = self.tcp_reader()
        wire = self.temperature_frame()
        sender.sendall(wire[:8])
        task = asyncio.create_task(reader.listen_forever())
        await asyncio.sleep(0.01)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertIsNone(reader._socket.gettimeout())
        sender.sendall(wire[8:])
        sender.shutdown(socket.SHUT_WR)
        await reader.listen_for(0.2)
        self.assertEqual(self.furnace(reader), 74.1)

    async def test_eof_after_unknown_packet_keeps_sensor_values(self):
        reader, sender = self.tcp_reader()
        sender.sendall(self.temperature_frame() + frame(87, bytes(24), sense=False))
        sender.shutdown(socket.SHUT_WR)
        await reader.listen_forever()
        self.assertEqual(self.furnace(reader), 74.1)
        self.assertIsNone(reader._sensors[PROP_PACKET_CTRL][0].value)

    async def test_serial_polling_and_timeout_restoration(self):
        class SerialInput:
            timeout = 5

            def __init__(self):
                self.data = deque()

            def read(self, size):
                if self.timeout != 0:
                    raise AssertionError('Serial read would block')
                return bytes((self.data.popleft(),)) if self.data else b''

            def close(self):
                pass

        reader = KWBEasyfire(-1)
        reader._debug_level = 0
        reader._mode = PROP_MODE_SERIAL
        reader._serial = SerialInput()

        async def feed():
            await asyncio.sleep(0.005)
            reader._serial.data.extend(self.temperature_frame())

        await asyncio.gather(reader.listen_for(0.05), feed())
        self.assertEqual(self.furnace(reader), 74.1)
        self.assertEqual(reader._serial.timeout, 5)

    async def test_zero_and_invalid_durations(self):
        reader, sender = self.tcp_reader()
        sender.sendall(self.temperature_frame())
        await reader.listen_for(0)
        self.assertIsNone(self.furnace(reader))
        for duration in (-1, float('inf'), float('nan')):
            with self.subTest(duration=duration), self.assertRaises(ValueError):
                await reader.listen_for(duration)
        sender.shutdown(socket.SHUT_WR)
        await reader.listen_forever()
        self.assertEqual(self.furnace(reader), 74.1)

    async def test_deadline_under_continuous_ready_input(self):
        reader = KWBEasyfire(-1)
        reader._debug_level = 0
        reader._mode = PROP_MODE_FILE
        # A ready source must still yield to cancellation, even without frames.
        with patch.object(reader, '_read_ord_byte', return_value=0):
            await reader.listen_for(0.02)
        reader._mode = -1


if __name__ == '__main__':
    unittest.main()
