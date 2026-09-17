"""Failure-path coverage complementing live-heater reconnect verification."""
import asyncio
import errno
import socket
import threading
import time
import unittest
from unittest.mock import AsyncMock, patch

from pykwb.kwb import KWBEasyfire, PROP_MODE_TCP
from test_temperatures import frame


def reader_with_config(**settings):
    reader = KWBEasyfire(-1, _config={'connection': {
        'reconnect': True, 'retry_initial': 0.005, 'retry_max': 0.01,
        'stale_timeout': 0.02, **settings}})
    reader._debug_level = 0
    reader._mode = PROP_MODE_TCP
    return reader


class ReconnectTests(unittest.TestCase):
    def test_initial_failure_is_retryable_only_when_enabled(self):
        for enabled in (False, True):
            with self.subTest(enabled=enabled), patch('pykwb.kwb.socket.socket') as factory:
                factory.return_value.connect_ex.return_value = errno.ECONNREFUSED
                if enabled:
                    reader = KWBEasyfire(PROP_MODE_TCP, _config={'connection': {'reconnect': True}})
                    self.assertIsNone(reader._socket)
                else:
                    with self.assertRaises(OSError):
                        KWBEasyfire(PROP_MODE_TCP)
                factory.return_value.close.assert_called()

    def test_backoff_caps_and_resets_only_on_valid_packet(self):
        reader = reader_with_config(retry_initial=1, retry_max=4)
        self.assertEqual([reader._next_retry_delay() for _ in range(4)], [1, 2, 4, 4])
        wire = frame(32, bytes(32))
        for byte in wire[:-1] + bytes((wire[-1] ^ 1,)):
            reader._consume_byte(byte)
        self.assertEqual(reader._next_retry_delay(), 4)
        for byte in wire:
            reader._consume_byte(byte)
        self.assertEqual(reader._next_retry_delay(), 1)

    def test_stop_interrupts_thread_retry_delay(self):
        reader = reader_with_config(retry_initial=10, retry_max=10)
        waiting = threading.Event()
        delay = reader._next_retry_delay

        def retry_delay():
            waiting.set()
            return delay()

        with patch.object(reader, '_next_retry_delay', side_effect=retry_delay), \
                patch.object(reader, '_connect_tcp') as connect:
            reader.run_thread()
            try:
                self.assertTrue(waiting.wait(1))
            finally:
                reader.stop_thread()
                reader._thread.join(1)
            self.assertFalse(reader.is_alive())
            connect.assert_not_called()

    def test_thread_stale_read_retries_and_invalidates(self):
        reader = reader_with_config()
        receiver, sender = socket.socketpair()
        reader._socket = receiver
        self.addCleanup(sender.close)
        self.addCleanup(reader._close_connection)
        reader._decode_sense_packet(32, bytes(73))

        def stop_retry():
            reader.stop_thread()
            raise ConnectionRefusedError()

        with patch.object(reader, '_connect_tcp', side_effect=stop_retry) as connect:
            reader.run_thread()
            reader._thread.join(1)
            if reader.is_alive():
                reader.stop_thread()
                reader._thread.join(1)
                self.fail('Stale read did not trigger reconnect')
            connect.assert_called_once()
        self.assertTrue(all(not s.available for s in reader.get_sensors()))
        self.assertIsNone(reader._packet_parser)
        self.assertEqual(receiver.fileno(), -1)

    def test_disconnect_discards_partial_packet(self):
        reader = reader_with_config()
        reader._decode_sense_packet(32, bytes(73))
        for byte in frame(32, bytes(73))[:10]:
            reader._consume_byte(byte)
        self.assertIsNotNone(reader._packet_parser)
        reader._connection_lost(ConnectionResetError())
        self.assertIsNone(reader._packet_parser)
        self.assertTrue(all(s.value is None and not s.available for s in reader.get_sensors()))


class AsyncReconnectTests(unittest.IsolatedAsyncioTestCase):
    async def test_stale_garbage_and_failed_retries_respect_deadline(self):
        reader = reader_with_config()
        receiver, sender = socket.socketpair()
        reader._socket = receiver
        self.addCleanup(sender.close)
        self.addCleanup(reader._close_connection)
        reader._decode_sense_packet(32, bytes(73))
        # Data is ready continuously, but it contains no valid packets.
        sender.sendall(bytes(2000))
        before = time.monotonic()
        with patch.object(reader, '_connect_tcp_async', new_callable=AsyncMock,
                          side_effect=ConnectionRefusedError()) as connect:
            await reader.listen_for(0.08)
            self.assertGreaterEqual(connect.await_count, 2)
        self.assertLess(time.monotonic() - before, 1)
        self.assertIsNone(reader._socket)
        self.assertTrue(all(not s.available for s in reader.get_sensors()))

    async def test_cancellation_closes_in_progress_connection(self):
        reader = reader_with_config()
        sock = socket.socket()
        loop = asyncio.get_running_loop()
        connecting = asyncio.Event()

        async def stall(*args):
            connecting.set()
            await asyncio.Event().wait()

        with patch('pykwb.kwb.socket.socket', return_value=sock), \
                patch.object(loop, 'sock_connect', side_effect=stall):
            task = asyncio.create_task(reader.listen_forever())
            await asyncio.wait_for(connecting.wait(), 1)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertEqual(sock.fileno(), -1)
        self.assertIsNone(reader._socket)

    async def test_default_does_not_reconnect_on_eof(self):
        reader = reader_with_config(reconnect=False)
        receiver, sender = socket.socketpair()
        reader._socket = receiver
        sender.close()
        self.addCleanup(reader._close_connection)
        with patch.object(reader, '_connect_tcp_async', new_callable=AsyncMock) as connect:
            await reader.listen_forever()
            connect.assert_not_awaited()
