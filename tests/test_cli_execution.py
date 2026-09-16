"""CLI execution mode selects the listener independently of its transport."""
import unittest
import asyncio
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import AsyncMock, Mock, patch

from pykwb.kwb import PROP_MODE_FILE, _listen_with_summaries, main


class CLIExecutionTests(unittest.TestCase):
    def test_forever_thread_summaries_and_shutdown(self):
        for summary in ('true', 'false'):
            with self.subTest(summary=summary), \
                    patch('sys.argv', ['kwb', '--forever', '--wait', '0.25',
                                       '--summary', summary]), \
                    patch('pykwb.kwb.KWBEasyfire') as factory, \
                    patch('pykwb.kwb.time.sleep', side_effect=[None, None, KeyboardInterrupt]) as sleep, \
                    patch('pykwb.kwb._print_summary') as report:
                main()
                self.assertEqual(report.call_count, 2 if summary == 'true' else 0)
                self.assertEqual(sleep.call_count, 3)
                factory.return_value.run_thread.assert_called_once_with()
                factory.return_value.stop_thread.assert_called_once_with()

    def test_forever_async_cli(self):
        with patch('sys.argv', ['kwb', '--forever', '--mode', 'async', '--wait', '0.25']), \
                patch('pykwb.kwb.KWBEasyfire') as factory, \
                patch('pykwb.kwb._listen_with_summaries', new_callable=AsyncMock) as listen:
            main()
            listen.assert_awaited_once_with(factory.return_value, 0.25, True)

    def test_async_summaries_do_not_restart_listener(self):
        async def check():
            eof = asyncio.Event()
            reader = Mock()
            reader.listen_forever = AsyncMock(side_effect=eof.wait)

            def report(_reader):
                if summary.call_count == 2:
                    eof.set()

            with patch('pykwb.kwb._print_summary', side_effect=report) as summary:
                await asyncio.wait_for(_listen_with_summaries(reader, 0.01, True), timeout=1)
                self.assertGreaterEqual(summary.call_count, 2)
            reader.listen_forever.assert_awaited_once_with()

        asyncio.run(check())

    def test_forever_requires_positive_interval(self):
        with patch('sys.argv', ['kwb', '--forever', '--wait', '0']), \
                patch('sys.stderr'), patch('pykwb.kwb.KWBEasyfire') as factory:
            with self.assertRaises(SystemExit) as error:
                main()
            self.assertEqual(error.exception.code, 2)
            factory.assert_not_called()

    def test_script_and_module_load_bundled_sensors(self):
        root = Path(__file__).resolve().parents[1]
        environment = os.environ.copy()
        environment.pop('PYTHONPATH', None)
        with tempfile.TemporaryDirectory() as directory:
            for command, cwd in (
                    ([sys.executable, str(root / 'pykwb' / 'kwb.py')], directory),
                    ([sys.executable, '-m', 'pykwb.kwb'], root)):
                with self.subTest(command=command):
                    result = subprocess.run(
                        command + ['--mode', 'async', '--wait', '0', '--log', 'false'],
                        cwd=cwd, env=environment, capture_output=True, text=True,
                        check=False, timeout=10,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('Heater Temp', result.stdout)

    def test_execution_modes(self):
        for options, asynchronous in (([], False), (['--mode', 'thread'], False),
                                      (['--mode', 'async'], True)):
            with self.subTest(options=options), \
                    patch('sys.argv', ['kwb', '--file', '--name', 'capture.txt',
                                       '--wait', '0.25', '--summary', 'false'] + options), \
                    patch('pykwb.kwb.KWBEasyfire') as factory, \
                    patch('pykwb.kwb.time.sleep') as sleep:
                reader = factory.return_value
                reader.listen_for = AsyncMock()
                main()
                self.assertEqual(factory.call_args.args[0], PROP_MODE_FILE)
                if asynchronous:
                    reader.listen_for.assert_awaited_once_with(seconds=0.25)
                    reader.run_thread.assert_not_called()
                    reader.stop_thread.assert_not_called()
                    sleep.assert_not_called()
                else:
                    reader.listen_for.assert_not_called()
                    reader.run_thread.assert_called_once_with()
                    sleep.assert_called_once_with(0.25)
                    reader.stop_thread.assert_called_once_with()
