import http.client
import json
import threading
import time
import unittest
import urllib.error
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


    def test_nothing_configured_no_probe(self):
        bare = [dict(SERVER, model=None), dict(LOCAL, model='')]
        with patch.object(keeper, 'connections', return_value=bare), \
             self._status({'server': 'ready', 'local': 'ready'}):
            self.assertIsNone(keeper.active(refresh=True))
        self.assertEqual(self.calls, 0)
        self.assertTrue(keeper.cached())

    def test_statuses_hanging_is_off(self):
        with self._status({'server': 'hang', 'local': 'stopped'}):
            start = time.monotonic()
            out = keeper.statuses([SERVER, LOCAL])
            took = time.monotonic() - start
        self.assertEqual(out, [('off', []), ('stopped', [])])
        self.assertLess(took, 1.0)

    def test_statuses_keep_order(self):
        with self._status({'server': 'no_models', 'local': 'ready'}):
            self.assertEqual(keeper.statuses([SERVER, LOCAL]), [('no_models', []), ('ready', [])])

    def test_statuses_empty(self):
        with self._status({}):
            self.assertEqual(keeper.statuses([]), [])
        self.assertEqual(self.calls, 0)


class Status(unittest.TestCase):
    def status(self, conn, answer=None, error=None, ollama='/usr/bin/ollama'):
        with patch.object(keeper, '_get_json', return_value=answer, side_effect=error) as get, \
             patch.object(keeper.shutil, 'which', return_value=ollama) as which:
            out = keeper.status(conn)
        self.assertEqual(get.call_args.args[1], '/api/tags')
        self.assertEqual(get.call_args.kwargs['timeout'], keeper.PROBE_TIMEOUT)
        return out, which

    def test_ready(self):
        out, _ = self.status(SERVER, {'models': [{'name': 'm'}, {'name': 'a'}]})
        self.assertEqual(out, ('ready', ['a', 'm']))

    def test_cyrillic_model(self):
        out, _ = self.status(dict(SERVER, model='модель:1b'), {'models': [{'name': 'модель:1b'}]})
        self.assertEqual(out, ('ready', ['модель:1b']))

    def test_bad_names_skipped(self):
        models = [{'name': 'b'}, {'name': ''}, {'name': 5}, {'name': None}, {}]
        out, _ = self.status(dict(SERVER, model=''), {'models': models})
        self.assertEqual(out, ('no_model', ['b']))

    def test_no_models(self):
        self.assertEqual(self.status(SERVER, {'models': []})[0], ('no_models', []))

    def test_model_missing(self):
        self.assertEqual(self.status(SERVER, {'models': [{'name': 'a'}]})[0], ('model_missing', ['a']))

    def test_server_off(self):
        for exc in (urllib.error.URLError('down'), OSError('down'), TimeoutError('slow')):
            with self.subTest(exc=exc):
                out, which = self.status(SERVER, error=exc)
                self.assertEqual(out, ('off', []))
                which.assert_not_called()

    def test_local_off(self):
        self.assertEqual(self.status(LOCAL, error=OSError('down'))[0], ('stopped', []))
        self.assertEqual(self.status(LOCAL, error=OSError('down'), ollama=None)[0], ('missing', []))

    def test_foreign_errors(self):
        for exc in (urllib.error.HTTPError('http://s/api/tags', 404, 'Not Found', None, None),
                    http.client.BadStatusLine('SSH-2.0'), json.JSONDecodeError('x', 'x', 0),
                    UnicodeDecodeError('utf-8', b'\xff', 0, 1, 'bad')):
            for conn in (SERVER, LOCAL):
                with self.subTest(exc=exc, slot=conn['slot']):
                    out, which = self.status(conn, error=exc)
                    self.assertEqual(out, ('foreign', []))
                    which.assert_not_called()

    def test_http_error_closed(self):
        exc = urllib.error.HTTPError('http://s/api/tags', 404, 'Not Found', None, None)
        with patch.object(exc, 'close', wraps=exc.close) as close:
            self.assertEqual(self.status(SERVER, error=exc)[0], ('foreign', []))
        close.assert_called_once_with()

    def test_foreign_shapes(self):
        for answer in ([], 'x', None, {}, {'models': None}, {'models': 'x'}, {'models': [None]}, {'models': ['m']}):
            with self.subTest(answer=answer):
                self.assertEqual(self.status(SERVER, answer)[0], ('foreign', []))
