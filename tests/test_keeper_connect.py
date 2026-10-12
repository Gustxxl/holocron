import threading
import time
import unittest
from unittest.mock import patch

from core import keeper

SERVER = {'slot': 'server', 'url': 'http://s', 'model': 'm'}
LOCAL = {'slot': 'local', 'url': 'http://l', 'model': 'm'}


class Probe(unittest.TestCase):
    def setUp(self):
        keeper.reset()
        self.addCleanup(keeper.reset)
        self.release = threading.Event()
        self.addCleanup(self.release.set)
        self.calls = 0
        for p in (patch.object(keeper, 'PROBE_TIMEOUT', 0.3),
                  patch.object(keeper, 'connections', return_value=[SERVER, LOCAL])):
            p.start()
            self.addCleanup(p.stop)

    def _status(self, states):
        def status(conn):
            self.calls += 1
            state = states[conn['slot']]
            if state == 'hang':
                self.release.wait(5)
                return 'off', []
            return state, []
        return patch.object(keeper, 'status', side_effect=status)

    def test_hanging_server_does_not_block(self):
        with self._status({'server': 'hang', 'local': 'ready'}):
            start = time.monotonic()
            conn = keeper.active(refresh=True)
            took = time.monotonic() - start
        self.assertEqual(conn, LOCAL)
        self.assertLess(took, 1.0)

    def test_server_preferred_when_both_ready(self):
        with self._status({'server': 'ready', 'local': 'ready'}):
            self.assertEqual(keeper.active(refresh=True), SERVER)

    def test_nothing_ready(self):
        with self._status({'server': 'off', 'local': 'stopped'}):
            self.assertIsNone(keeper.active(refresh=True))
        self.assertTrue(keeper.cached())

    def test_cache_skips_probe(self):
        with self._status({'server': 'off', 'local': 'ready'}):
            keeper.active(refresh=True)
            calls = self.calls
            self.assertEqual(keeper.active(), LOCAL)
            self.assertEqual(self.calls, calls)
            keeper.active(refresh=True)
            self.assertGreater(self.calls, calls)

    def test_reset_clears_cache(self):
        with self._status({'server': 'off', 'local': 'ready'}):
            keeper.active(refresh=True)
        keeper.reset()
        self.assertFalse(keeper.cached())
