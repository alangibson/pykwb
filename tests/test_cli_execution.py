"""CLI execution mode selects the listener independently of its transport."""
import unittest
from unittest.mock import AsyncMock, patch

from pykwb.kwb import PROP_MODE_FILE, main


class CLIExecutionTests(unittest.TestCase):
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
