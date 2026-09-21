"""Async connection lifecycle and packet-health reconnect coverage."""
import asyncio
import time
import unittest
from unittest.mock import AsyncMock, Mock, patch

from pykwb.kwb import KWBEasyfire, PROP_MODE_TCP
from test_temperatures import frame


def reader_with_config(**settings):
    reader = KWBEasyfire(PROP_MODE_TCP, _config={'connection': {
        'reconnect': True, 'retry_initial': 0.005, 'retry_max': 0.01,
        'stale_timeout': 0.02, **settings}})
    reader._debug_level = 0
    return reader


def stream_pair():
    writer = Mock()
    writer.wait_closed = AsyncMock()
    return asyncio.StreamReader(), writer


class ReconnectTests(unittest.IsolatedAsyncioTestCase):
    async def test_initial_failure_is_retryable_only_when_enabled(self):
        for enabled in (False, True):
            with self.subTest(enabled=enabled), patch(
                    'pykwb.kwb.asyncio.open_connection', new_callable=AsyncMock,
                    side_effect=ConnectionRefusedError()) as connect:
                reader = reader_with_config(reconnect=enabled)
                connect.assert_not_called()
                if enabled:
                    await reader.listen_for(0.05)
                    self.assertGreaterEqual(connect.await_count, 2)
                else:
                    with self.assertRaises(ConnectionRefusedError):
                        await reader.listen_forever()
                    connect.assert_awaited_once()
                await reader.close()

    async def test_backoff_caps_and_resets_only_on_valid_packet(self):
        reader = reader_with_config(retry_initial=1, retry_max=4)
        self.assertEqual([reader._next_retry_delay() for _ in range(4)], [1, 2, 4, 4])
        wire = frame(32, bytes(32))
        for byte in wire[:-1] + bytes((wire[-1] ^ 1,)):
            reader._consume_byte(byte)
        self.assertEqual(reader._next_retry_delay(), 4)
        for byte in wire:
            reader._consume_byte(byte)
        self.assertEqual(reader._next_retry_delay(), 1)

    async def test_cancellation_interrupts_retry_delay(self):
        reader = reader_with_config(retry_initial=10, retry_max=10)
        with patch.object(reader, '_open_connection', new_callable=AsyncMock,
                          side_effect=ConnectionRefusedError()) as connect:
            await asyncio.wait_for(reader.listen_for(0.02), 1)
            connect.assert_awaited_once()

    async def test_disconnect_discards_partial_packet_and_closes_stream(self):
        reader = reader_with_config()
        reader._reader, reader._writer = stream_pair()
        writer = reader._writer
        reader._decode_sense_packet(32, bytes(73))
        for byte in frame(32, bytes(73))[:10]:
            reader._consume_byte(byte)
        self.assertIsNotNone(reader._packet_parser)
        await reader._connection_lost(ConnectionResetError())
        self.assertIsNone(reader._packet_parser)
        self.assertIsNone(reader._reader)
        self.assertTrue(all(s.value is None and not s.available for s in reader.get_sensors()))
        writer.close.assert_called_once()
        writer.wait_closed.assert_awaited_once()

    async def test_stale_garbage_and_failed_retries_respect_deadline(self):
        reader = reader_with_config()
        reader._reader, reader._writer = stream_pair()
        reader._reader.feed_data(bytes(2000))
        reader._decode_sense_packet(32, bytes(73))
        before = time.monotonic()
        with patch.object(reader, '_open_connection', new_callable=AsyncMock,
                          side_effect=ConnectionRefusedError()) as connect:
            await reader.listen_for(0.08)
            self.assertGreaterEqual(connect.await_count, 2)
        self.assertLess(time.monotonic() - before, 1)
        self.assertIsNone(reader._reader)
        self.assertTrue(all(not s.available for s in reader.get_sensors()))

    async def test_connect_timeout_and_cancellation(self):
        for cancel in (False, True):
            reader = reader_with_config(reconnect=False, connect_timeout=0.02)
            connecting, cleaned = asyncio.Event(), asyncio.Event()

            async def stall(*args):
                connecting.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    cleaned.set()

            with self.subTest(cancel=cancel), patch(
                    'pykwb.kwb.asyncio.open_connection', side_effect=stall):
                task = asyncio.create_task(reader.listen_forever())
                await asyncio.wait_for(connecting.wait(), 1)
                if cancel:
                    task.cancel()
                with self.assertRaises(asyncio.CancelledError if cancel else asyncio.TimeoutError):
                    await task
                self.assertTrue(cleaned.is_set())
                self.assertIsNone(reader._reader)
                self.assertIsNone(reader._writer)

    async def test_listen_for_propagates_connection_timeout(self):
        reader = reader_with_config(reconnect=False, connect_timeout=0.01)

        async def stall(*args):
            await asyncio.Event().wait()

        with patch('pykwb.kwb.asyncio.open_connection', side_effect=stall):
            with self.assertRaises(asyncio.TimeoutError):
                await reader.listen_for(1)

    async def test_default_does_not_reconnect_on_eof(self):
        reader = reader_with_config(reconnect=False)
        reader._reader, reader._writer = stream_pair()
        reader._reader.feed_eof()
        with patch.object(reader, '_open_connection', new_callable=AsyncMock) as connect:
            await reader.listen_forever()
            connect.assert_not_awaited()
        self.assertIsNone(reader._reader)

    async def test_reconnect_receives_fresh_packet(self):
        reader = reader_with_config()
        first, first_writer = stream_pair()
        second, second_writer = stream_pair()
        first.feed_data(frame(32, bytes(32))[:8])
        first.feed_eof()
        payload = bytearray(32)
        payload[12:14] = b'\x02\xe5'
        second.feed_data(frame(32, payload))
        with patch('pykwb.kwb.asyncio.open_connection', new_callable=AsyncMock,
                   side_effect=[(first, first_writer), (second, second_writer)]) as connect:
            await reader.listen_for(0.015)
            self.assertEqual(connect.await_count, 2)
            self.assertEqual(next(s.value for s in reader.get_sensors() if s.key == 'heater_temp'), 74.1)
        first_writer.close.assert_called_once()
        await reader.close()
        second_writer.close.assert_called_once()
